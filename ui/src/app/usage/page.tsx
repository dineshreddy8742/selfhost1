"use client";

import { Check, ChevronLeft, ChevronRight, Download, Globe, Pencil } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useId, useState } from 'react';
import TimezoneSelect, { type ITimezoneOption } from 'react-timezone-select';
import { toast } from 'sonner';

import { downloadUsageRunsReportApiV1OrganizationsUsageRunsReportGet, getDailyUsageBreakdownApiV1OrganizationsUsageDailyBreakdownGet, getPreferencesApiV1OrganizationsPreferencesGet, getUsageHistoryApiV1OrganizationsUsageRunsGet, savePreferencesApiV1OrganizationsPreferencesPut } from '@/client/sdk.gen';
import type { DailyUsageBreakdownResponse, OrganizationPreferences, UsageHistoryResponse, WorkflowRunUsageResponse } from '@/client/types.gen';
import { CallTypeCell } from '@/components/CallTypeCell';
import { DailyUsageTable } from '@/components/DailyUsageTable';
import { FilterBuilder } from '@/components/filters/FilterBuilder';
import { MediaPreviewButton, MediaPreviewDialog } from '@/components/MediaPreviewDialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';
import { useUserConfig } from '@/context/UserConfigContext';
import { useAuth } from '@/lib/auth';
import { usageFilterAttributes } from '@/lib/filterAttributes';
import { decodeFiltersFromURL, encodeFiltersToURL } from '@/lib/filters';
import { ActiveFilter, DateRangeValue } from '@/types/filters';

// Get local timezone
const getLocalTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

export default function UsagePage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { organizationPricing } = useUserConfig();
    const auth = useAuth();

    // Usage history state
    const [usageHistory, setUsageHistory] = useState<UsageHistoryResponse | null>(null);
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);
    const [currentPage, setCurrentPage] = useState(() => {
        const pageParam = searchParams.get('page');
        return pageParam ? parseInt(pageParam, 10) : 1;
    });
    const [isExecutingFilters, setIsExecutingFilters] = useState(false);
    const [isDownloadingReport, setIsDownloadingReport] = useState(false);

    // Track manual intent edits
    const [editIntentMap, setEditIntentMap] = useState<Record<number, string>>({});
    const [editingRunId, setEditingRunId] = useState<number | null>(null);
    const [savingRunId, setSavingRunId] = useState<number | null>(null);

    const handleSaveIntent = async (run: WorkflowRunUsageResponse, newIntent: string) => {
        setSavingRunId(run.id);
        setEditingRunId(null);
        // Optimistically update intent map so user sees immediate feedback
        setEditIntentMap(prev => ({ ...prev, [run.id]: newIntent }));
        toast.success(`Intent updated to ${newIntent}`);
        try {
            const workflowId = run.workflow_id || (run as any).workflowId || 0;
            const token = await auth.getAccessToken();
            await fetch(`/api/v1/workflow/${workflowId}/runs/${run.id}/intent`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                body: JSON.stringify({ intent: newIntent }),
            });
        } catch (_) {
            // optimistic state maintained
        } finally {
            setSavingRunId(null);
        }
    };

    // Daily usage breakdown state (only for paid orgs)
    const [dailyUsage, setDailyUsage] = useState<DailyUsageBreakdownResponse | null>(null);
    const [isLoadingDaily, setIsLoadingDaily] = useState(false);

    // Initialize filters from URL. `activeFilters` tracks the in-progress
    // edits in the FilterBuilder; `appliedFilters` is what's actually been
    // committed via Apply (and what drives fetching + the download button).
    const [activeFilters, setActiveFilters] = useState<ActiveFilter[]>(() => {
        return decodeFiltersFromURL(searchParams, usageFilterAttributes);
    });
    const [appliedFilters, setAppliedFilters] = useState<ActiveFilter[]>(() => {
        return decodeFiltersFromURL(searchParams, usageFilterAttributes);
    });

    // Media preview dialog
    const mediaPreview = MediaPreviewDialog();

    // Timezone state - initialize with empty string to avoid hydration mismatch
    const localTimezone = getLocalTimezone();
    const [selectedTimezone, setSelectedTimezone] = useState<ITimezoneOption | string>('');
    const [savingTimezone, setSavingTimezone] = useState(false);
    const [preferences, setPreferences] = useState<OrganizationPreferences>({});
    const [preferencesLoading, setPreferencesLoading] = useState(true);
    const timezoneSelectId = useId(); // Stable ID for react-select to prevent hydration mismatch

    // Translate the FilterBuilder state into the query-param shape the
    // backend expects. Shared between the listing fetch and the CSV export
    // so they stay in lockstep.
    const buildUsageQueryParams = (filters?: ActiveFilter[]) => {
        let filterParam: string | undefined;
        let startDate = '';
        let endDate = '';

        if (filters && filters.length > 0) {
            const dateRangeFilter = filters.find(f => f.attribute.id === 'dateRange');
            if (dateRangeFilter && dateRangeFilter.value) {
                const dateValue = dateRangeFilter.value as DateRangeValue;
                if (dateValue.from) startDate = dateValue.from.toISOString();
                if (dateValue.to) endDate = dateValue.to.toISOString();
            }

            const otherFilters = filters.filter(f => f.attribute.id !== 'dateRange');
            if (otherFilters.length > 0) {
                const filterData = otherFilters.map(filter => ({
                    attribute: filter.attribute.id,
                    type: filter.attribute.type,
                    value: filter.value,
                }));
                filterParam = JSON.stringify(filterData);
            }
        }

        return {
            ...(startDate && { start_date: startDate }),
            ...(endDate && { end_date: endDate }),
            ...(filterParam && { filters: filterParam }),
        };
    };

    // Fetch usage history
    const fetchUsageHistory = useCallback(async (page: number, filters?: ActiveFilter[]) => {
        if (!auth.isAuthenticated) return;
        setIsLoadingHistory(true);
        try {
            const response = await getUsageHistoryApiV1OrganizationsUsageRunsGet({
                query: {
                    page,
                    limit: 50,
                    ...buildUsageQueryParams(filters),
                },
            });

            if (response.data) {
                setUsageHistory(response.data);
            }
        } catch (error) {
            console.error('Failed to fetch usage history:', error);
        } finally {
            setIsLoadingHistory(false);
        }
    }, [auth.isAuthenticated]);

    // Fetch daily usage breakdown
    const fetchDailyUsage = useCallback(async () => {
        if (!auth.isAuthenticated || !organizationPricing?.price_per_second_usd) return;

        setIsLoadingDaily(true);
        try {
            const response = await getDailyUsageBreakdownApiV1OrganizationsUsageDailyBreakdownGet({
                query: { days: 7 },
            });

            if (response.data) {
                setDailyUsage(response.data);
            }
        } catch (error) {
            console.error('Failed to fetch daily usage:', error);
        } finally {
            setIsLoadingDaily(false);
        }
    }, [auth.isAuthenticated, organizationPricing]);

    const fetchPreferences = useCallback(async () => {
        if (!auth.isAuthenticated) return;

        setPreferencesLoading(true);
        try {
            const response = await getPreferencesApiV1OrganizationsPreferencesGet();
            const nextPreferences = response.data || {};
            setPreferences(nextPreferences);
            setSelectedTimezone(nextPreferences.timezone || localTimezone);
        } catch (error) {
            console.error('Failed to fetch organization preferences:', error);
            setSelectedTimezone(localTimezone);
        } finally {
            setPreferencesLoading(false);
        }
    }, [auth.isAuthenticated, localTimezone]);

    // Download an Excel workbook of all runs matching the current filters.
    const handleDownloadReport = async () => {
        if (!auth.isAuthenticated) return;
        setIsDownloadingReport(true);
        try {
            const response = await downloadUsageRunsReportApiV1OrganizationsUsageRunsReportGet({
                query: buildUsageQueryParams(appliedFilters),
                parseAs: 'blob',
            });

            if (response.data) {
                const blob = response.data as Blob;
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'usage_runs_report.xlsx';
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            } else {
                toast.error('Failed to download report');
            }
        } catch (error) {
            console.error('Failed to download usage report:', error);
            toast.error('Failed to download report');
        } finally {
            setIsDownloadingReport(false);
        }
    };

    // Handle timezone change
    const handleTimezoneChange = async (timezone: ITimezoneOption | string) => {
        setSelectedTimezone(timezone);
        setSavingTimezone(true);
        const previousTimezone = preferences.timezone || localTimezone;
        try {
            const tzValue = typeof timezone === 'string' ? timezone : timezone.value;
            const response = await savePreferencesApiV1OrganizationsPreferencesPut({
                body: {
                    ...preferences,
                    timezone: tzValue,
                },
            });
            if (response.error) {
                throw new Error('Failed to save timezone');
            }
            setPreferences(response.data || { ...preferences, timezone: tzValue });
        } catch (error) {
            console.error('Failed to save timezone:', error);
            setSelectedTimezone(previousTimezone);
        } finally {
            setSavingTimezone(false);
        }
    };

    // Update timezone when organization preferences load.
    useEffect(() => {
        fetchPreferences();
    }, [fetchPreferences]);

    // Initial load - fetch when auth becomes available
    useEffect(() => {
        if (auth.isAuthenticated) {
            fetchUsageHistory(currentPage, appliedFilters);
        }
    }, [auth.isAuthenticated, currentPage, appliedFilters, fetchUsageHistory]);

    // Fetch daily usage when organizationPricing becomes available
    useEffect(() => {
        if (auth.isAuthenticated && organizationPricing?.price_per_second_usd) {
            fetchDailyUsage();
        }
    }, [auth.isAuthenticated, organizationPricing, fetchDailyUsage]);

    // Update URL with query parameters
    const updateUrlParams = useCallback((params: { page?: number; filters?: ActiveFilter[] }) => {
        const newParams = new URLSearchParams();

        if (params.page !== undefined) {
            newParams.set('page', params.page.toString());
        }

        // Add filters to URL if present
        if (params.filters && params.filters.length > 0) {
            const filterString = encodeFiltersToURL(params.filters);
            if (filterString) {
                const filterParams = new URLSearchParams(filterString);
                filterParams.forEach((value, key) => newParams.set(key, value));
            }
        }

        router.push(`/usage?${newParams.toString()}`);
    }, [router]);

    const handleApplyFilters = useCallback(async () => {
        setIsExecutingFilters(true);
        setCurrentPage(1); // Reset to first page when applying filters
        setAppliedFilters(activeFilters);
        updateUrlParams({ page: 1, filters: activeFilters });
        await fetchUsageHistory(1, activeFilters);
        setIsExecutingFilters(false);
    }, [activeFilters, fetchUsageHistory, updateUrlParams]);

    const handleFiltersChange = useCallback((filters: ActiveFilter[]) => {
        setActiveFilters(filters);
    }, []);

    const handleClearFilters = useCallback(async () => {
        setIsExecutingFilters(true);
        setCurrentPage(1);
        setActiveFilters([]);
        setAppliedFilters([]);
        updateUrlParams({ page: 1, filters: [] }); // Clear filters from URL
        await fetchUsageHistory(1, []); // Fetch all runs without filters
        setIsExecutingFilters(false);
    }, [fetchUsageHistory, updateUrlParams]);

    // Handle page change
    const handlePageChange = (newPage: number) => {
        setCurrentPage(newPage);
        updateUrlParams({ page: newPage, filters: appliedFilters });
        fetchUsageHistory(newPage, appliedFilters);
    };

    // Handle row click to navigate to workflow run
    const handleRowClick = (run: WorkflowRunUsageResponse) => {
        router.push(`/workflow/${run.workflow_id}/run/${run.id}`);
    };

    // Format datetime for display with timezone support
    const formatDateTime = (dateString: string) => {
        const date = new Date(dateString);
        const tzValue = typeof selectedTimezone === 'string' ? selectedTimezone : selectedTimezone.value;
        // Use local timezone if none selected (during loading)
        const effectiveTz = tzValue || localTimezone;
        return date.toLocaleString('en-US', {
            timeZone: effectiveTz,
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        });
    };

    // Format duration for display
    const formatDuration = (seconds: number) => {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        if (minutes === 0) return `${remainingSeconds}s`;
        if (remainingSeconds === 0) return `${minutes}m`;
        return `${minutes}m ${remainingSeconds}s`;
    };

    return (
        <div className="container mx-auto p-6 space-y-6">
            <div>
                <div className="flex justify-between items-start">
                    <div>
                        <h1 className="text-3xl font-bold mb-2">Agent Runs</h1>
                        <p className="text-muted-foreground">See all your Agent Runs across all Voice Agents. You can use filters to filter out required Agent Runs.</p>
                    </div>
                        <div className="flex items-center gap-2">
                            <Globe className="h-4 w-4 text-muted-foreground" />
                            <div className="w-[300px]">
                                <TimezoneSelect
                                    instanceId={timezoneSelectId}
                                    value={selectedTimezone}
                                    onChange={handleTimezoneChange}
                                    isDisabled={savingTimezone || preferencesLoading}
                                    placeholder={preferencesLoading ? "Loading..." : "Select timezone"}
                                    styles={{
                                        control: (base, state) => ({
                                            ...base,
                                            minHeight: '36px',
                                            fontSize: '14px',
                                            backgroundColor: 'var(--background)',
                                            borderColor: state.isFocused ? 'var(--ring)' : 'var(--border)',
                                            boxShadow: state.isFocused ? '0 0 0 2px color-mix(in srgb, var(--ring) 20%, transparent)' : 'none',
                                            '&:hover': {
                                                borderColor: 'var(--border)',
                                            },
                                        }),
                                        menu: (base) => ({
                                            ...base,
                                            zIndex: 9999,
                                            backgroundColor: 'var(--popover)',
                                            border: '1px solid var(--border)',
                                            boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
                                        }),
                                        menuList: (base) => ({
                                            ...base,
                                            backgroundColor: 'var(--popover)',
                                            padding: 0,
                                        }),
                                        option: (base, state) => ({
                                            ...base,
                                            backgroundColor: state.isSelected
                                                ? 'var(--accent)'
                                                : state.isFocused
                                                ? 'var(--accent)'
                                                : 'var(--popover)',
                                            color: 'var(--foreground)',
                                            cursor: 'pointer',
                                            '&:active': {
                                                backgroundColor: 'var(--accent)',
                                            },
                                        }),
                                        singleValue: (base) => ({
                                            ...base,
                                            color: 'var(--foreground)',
                                        }),
                                        input: (base) => ({
                                            ...base,
                                            color: 'var(--foreground)',
                                        }),
                                        placeholder: (base) => ({
                                            ...base,
                                            color: 'var(--muted-foreground)',
                                        }),
                                        indicatorSeparator: (base) => ({
                                            ...base,
                                            backgroundColor: 'var(--border)',
                                        }),
                                        dropdownIndicator: (base) => ({
                                            ...base,
                                            color: 'var(--muted-foreground)',
                                            '&:hover': {
                                                color: 'var(--foreground)',
                                            },
                                        }),
                                    }}
                                />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Daily Usage Table - Only for paid organizations */}
                {organizationPricing?.price_per_second_usd && (
                    <div className="mb-6">
                        <DailyUsageTable
                            data={dailyUsage}
                            isLoading={isLoadingDaily}
                        />
                    </div>
                )}

                {/* Filter Builder */}
                <div className="mb-6 space-y-3">
                    <FilterBuilder
                        availableAttributes={usageFilterAttributes}
                        activeFilters={activeFilters}
                        onFiltersChange={handleFiltersChange}
                        onApplyFilters={handleApplyFilters}
                        onClearFilters={handleClearFilters}
                        isExecuting={isExecutingFilters}
                    />
                    {appliedFilters.length > 0 && (
                        <div className="flex justify-end">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleDownloadReport}
                                disabled={isDownloadingReport}
                            >
                                <Download className="h-4 w-4 mr-2" />
                                {isDownloadingReport ? 'Preparing...' : 'Download Filtered Results'}
                            </Button>
                        </div>
                    )}
                </div>

                {/* Usage History */}
                <Card>
                    <CardHeader>
                        <div className="flex justify-between items-start">
                            <div className="space-y-1.5">
                                <CardTitle>All Runs</CardTitle>
                                <CardDescription>
                                    Every agent run across your organization, with usage details
                                </CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent>
                        {isLoadingHistory ? (
                            <div className="animate-pulse space-y-3">
                                {[...Array(5)].map((_, i) => (
                                    <div key={i} className="h-12 bg-muted rounded"></div>
                                ))}
                            </div>
                        ) : usageHistory && usageHistory.runs.length > 0 ? (
                            <>
                                <div className="bg-card border rounded-lg overflow-hidden shadow-sm">
                                    <Table>
                                        <TableHeader>
                                            <TableRow className="bg-muted/50">
                                                <TableHead className="font-semibold">Run ID</TableHead>
                                                <TableHead className="font-semibold">Agent Name</TableHead>
                                                <TableHead className="font-semibold">Call Type</TableHead>
                                                <TableHead className="font-semibold">Phone Number</TableHead>
                                                <TableHead className="font-semibold">Disposition</TableHead>
                                                <TableHead className="font-semibold">Intent</TableHead>
                                                <TableHead className="font-semibold">Date</TableHead>
                                                <TableHead className="font-semibold text-right">Duration</TableHead>
                                                {organizationPricing?.price_per_second_usd && (
                                                    <TableHead className="font-semibold text-right">Cost (USD)</TableHead>
                                                )}
                                                <TableHead className="font-semibold">Actions</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {usageHistory.runs.map((run) => {
                                                const gc = (run.gathered_context || {}) as Record<string, any>;
                                                const rawIntent = ((run as any).user_intent || gc.user_intent || gc.intent || gc.interest_level || gc.interest) as string | undefined;
                                                let userIntent = rawIntent;
                                                if (!userIntent) {
                                                    if (gc.user_qualified === true || run.disposition === 'user_qualified') {
                                                        userIntent = 'Interested';
                                                    } else if (gc.user_qualified === false || run.disposition === 'disqualified') {
                                                        userIntent = 'Not Interested';
                                                    } else if (['busy', 'no-answer', 'failed', 'canceled', 'cancelled', 'initialized'].includes((run.disposition || '').toLowerCase())) {
                                                        userIntent = 'Not Connected';
                                                    } else {
                                                        userIntent = 'Not Interested';
                                                    }
                                                }
                                                return (
                                                <TableRow
                                                    key={run.id}
                                                >
                                                    <TableCell
                                                        className="font-mono text-sm cursor-pointer hover:underline"
                                                        onClick={() => handleRowClick(run)}
                                                    >
                                                        #{run.id}
                                                    </TableCell>
                                                    <TableCell>{run.workflow_name || 'Unknown'}</TableCell>
                                                    <TableCell>
                                                        <CallTypeCell mode={run.mode} callType={run.call_type} />
                                                    </TableCell>
                                                    <TableCell className="text-sm">
                                                        {(run.call_type === 'inbound'
                                                            ? run.caller_number
                                                            : run.called_number) || '-'}
                                                    </TableCell>
                                                    <TableCell>
                                                        {run.disposition ? (
                                                            <Badge variant="default">
                                                                {run.disposition}
                                                            </Badge>
                                                        ) : (
                                                            <span className="text-sm text-muted-foreground">-</span>
                                                        )}
                                                    </TableCell>
                                                     <TableCell onClick={(e) => e.stopPropagation()}>
                                                         <div className="relative inline-block text-left">
                                                             {(() => {
                                                                 const currentVal = editIntentMap[run.id] || userIntent || 'Not Interested';
                                                                 const getIntentStyle = (val: string) => {
                                                                     const s = (val || '').toLowerCase();
                                                                     if (s.includes('interested') && !s.includes('not')) {
                                                                         return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/25';
                                                                     }
                                                                     if (s.includes('positive') || s.includes('confirmed') || s.includes('qualified') || s.includes('hot')) {
                                                                         return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/25';
                                                                     }
                                                                     if (s.includes('not connected') || s.includes('busy') || s.includes('failed') || s.includes('canceled') || s.includes('no-answer')) {
                                                                         return 'bg-slate-500/15 text-slate-600 dark:text-slate-300 border-slate-500/40 hover:bg-slate-500/25';
                                                                     }
                                                                     if (s.includes('not interested') || s.includes('negative') || s.includes('disqualified') || s.includes('declined')) {
                                                                         return 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/40 hover:bg-rose-500/25';
                                                                     }
                                                                     if (s.includes('grievance') || s.includes('complaint')) {
                                                                         return 'bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/40 hover:bg-purple-500/25';
                                                                     }
                                                                     if (s.includes('callback') || s.includes('follow')) {
                                                                         return 'bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/40 hover:bg-blue-500/25';
                                                                     }
                                                                     if (s.includes('neutral') || s.includes('inquiry')) {
                                                                         return 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40 hover:bg-amber-500/25';
                                                                     }
                                                                     return 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border-indigo-500/40 hover:bg-indigo-500/25';
                                                                 };

                                                                 const intentOptions = [
                                                                     'Interested',
                                                                     'Not Interested',
                                                                     'Positive',
                                                                     'Negative',
                                                                     'Neutral',
                                                                     'Grievance',
                                                                     'Callback Requested',
                                                                     'Inquiry',
                                                                     'Not Connected',
                                                                 ] as const;

                                                                 return (
                                                                     <>
                                                                         <button
                                                                             type="button"
                                                                             onClick={() => setEditingRunId(editingRunId === run.id ? null : run.id)}
                                                                             className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border transition-all cursor-pointer hover:scale-105 hover:shadow-sm ${getIntentStyle(currentVal)}`}
                                                                             title="Click to edit intent"
                                                                         >
                                                                             <span>{currentVal}</span>
                                                                             <Pencil className="h-3 w-3 opacity-70" />
                                                                         </button>

                                                                         {savingRunId === run.id && (
                                                                             <span className="text-muted-foreground text-xs animate-pulse ml-1.5">saving…</span>
                                                                         )}

                                                                         {editingRunId === run.id && (
                                                                             <div className="absolute top-8 left-0 z-50 bg-background border border-border rounded-lg shadow-xl py-1 min-w-[170px] max-h-60 overflow-y-auto">
                                                                                 {intentOptions.map((opt) => (
                                                                                     <button
                                                                                         key={opt}
                                                                                         onClick={() => handleSaveIntent(run, opt)}
                                                                                         className="flex items-center gap-2 w-full px-3 py-1.5 text-xs font-medium hover:bg-muted text-left transition-colors"
                                                                                     >
                                                                                         {currentVal === opt ? <Check className="h-3.5 w-3.5 text-emerald-500 shrink-0" /> : <span className="w-3.5" />}
                                                                                         <span className={opt === 'Interested' || opt === 'Positive' ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : opt === 'Not Interested' || opt === 'Negative' ? 'text-rose-600 dark:text-rose-400 font-semibold' : opt === 'Grievance' ? 'text-purple-600 dark:text-purple-400 font-semibold' : opt === 'Callback Requested' ? 'text-blue-600 dark:text-blue-400 font-semibold' : opt === 'Neutral' || opt === 'Inquiry' ? 'text-amber-600 dark:text-amber-400 font-semibold' : 'text-slate-500'}>
                                                                                             {opt}
                                                                                         </span>
                                                                                     </button>
                                                                                 ))}
                                                                             </div>
                                                                         )}
                                                                     </>
                                                                 );
                                                             })()}
                                                         </div>
                                                     </TableCell>
                                                    <TableCell>{formatDateTime(run.created_at)}</TableCell>
                                                    <TableCell className="text-right">
                                                        {formatDuration(run.call_duration_seconds)}
                                                    </TableCell>
                                                    {organizationPricing?.price_per_second_usd && (
                                                        <TableCell className="text-right font-medium">
                                                            {run.charge_usd !== undefined && run.charge_usd !== null
                                                                ? `$${run.charge_usd.toFixed(2)}`
                                                                : '-'
                                                            }
                                                        </TableCell>
                                                    )}
                                                    <TableCell>
                                                        <MediaPreviewButton
                                                            recordingUrl={run.recording_url}
                                                            transcriptUrl={run.transcript_url}
                                                            runId={run.id}
                                                            onOpenPreview={mediaPreview.openPreview}
                                                        />
                                                    </TableCell>
                                                </TableRow>
                                                ); })}
                                        </TableBody>
                                    </Table>
                                </div>

                                {/* Summary */}
                                {appliedFilters.length > 0 && (
                                    <div className="mt-4 p-3 bg-muted rounded-md">
                                        <p className="text-sm text-muted-foreground">
                                            Total for filtered period: <span className="font-semibold text-foreground">
                                                {usageHistory.total_dograh_tokens.toLocaleString()} Dailsmart Tokens
                                            </span>
                                            {' • '}
                                            <span className="font-semibold text-foreground">
                                                {formatDuration(usageHistory.total_duration_seconds)}
                                            </span>
                                        </p>
                                    </div>
                                )}

                                {/* Pagination */}
                                {usageHistory.total_pages > 1 && (
                                    <div className="flex items-center justify-between mt-6">
                                        <p className="text-sm text-muted-foreground">
                                            Page {usageHistory.page} of {usageHistory.total_pages} ({usageHistory.total_count} total runs)
                                        </p>
                                        <div className="flex gap-2">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => handlePageChange(currentPage - 1)}
                                                disabled={currentPage === 1}
                                            >
                                                <ChevronLeft className="h-4 w-4" />
                                                Previous
                                            </Button>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => handlePageChange(currentPage + 1)}
                                                disabled={currentPage === usageHistory.total_pages}
                                            >
                                                Next
                                                <ChevronRight className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    </div>
                                )}
                            </>
                        ) : (
                            <p className="text-center py-8 text-muted-foreground">No runs found</p>
                        )}
                    </CardContent>
                </Card>

                {/* Media Preview Dialog */}
                {mediaPreview.dialog}
        </div>
    );
}
