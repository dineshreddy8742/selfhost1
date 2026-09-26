"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, Check, ChevronLeft, ChevronRight, ExternalLink, Pencil, RefreshCw } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { WorkflowRunResponseSchema } from "@/client/types.gen";
import { CallTypeCell } from "@/components/CallTypeCell";
import { FilterBuilder } from "@/components/filters/FilterBuilder";
import { MediaPreviewButton, MediaPreviewDialog } from "@/components/MediaPreviewDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { ActiveFilter, FilterAttribute } from "@/types/filters";
import { useAuth } from "@/lib/auth";

export interface WorkflowRunsTableProps {
    // Data
    runs: WorkflowRunResponseSchema[];
    loading: boolean;
    error: string | null;

    // Pagination
    currentPage: number;
    totalPages: number;
    totalCount: number;
    onPageChange: (page: number) => void;

    // Filters
    availableAttributes: FilterAttribute[];
    activeFilters: ActiveFilter[];
    onFiltersChange: (filters: ActiveFilter[]) => void;
    onApplyFilters: () => void;
    onClearFilters: () => void;
    isExecutingFilters: boolean;
    hasAppliedFilters?: boolean;

    // Sorting
    sortBy?: string | null;
    sortOrder?: 'asc' | 'desc';
    onSort?: (field: string) => void;

    // Navigation & Actions
    workflowId: number;

    // Reload
    onReload?: () => void;

    // Optional customization
    title?: string;
    subtitle?: string;
    showFilters?: boolean;
    emptyMessage?: string;
}

const getCallStatusBadge = (run: WorkflowRunResponseSchema) => {
    if (run.is_completed) {
        const disposition = run.gathered_context?.mapped_call_disposition;
        if (disposition === 'no-answer') {
            return <Badge className="bg-amber-500 hover:bg-amber-600 text-white border-none">No Answer</Badge>;
        }
        if (disposition === 'busy') {
            return <Badge className="bg-amber-500 hover:bg-amber-600 text-white border-none">Busy</Badge>;
        }
        if (disposition === 'canceled') {
            return <Badge className="bg-amber-500 hover:bg-amber-600 text-white border-none">Canceled</Badge>;
        }
        if (disposition === 'failed' || disposition === 'error') {
            return <Badge variant="destructive">Failed</Badge>;
        }
        return <Badge className="bg-emerald-500 hover:bg-emerald-600 text-white border-none">Completed</Badge>;
    }

    const callbacks = run.logs?.telephony_status_callbacks;
    if (Array.isArray(callbacks) && callbacks.length > 0) {
        const latestCallback = callbacks[callbacks.length - 1];
        const status = latestCallback?.status;
        if (status === 'ringing') {
            return <Badge className="bg-blue-500 hover:bg-blue-600 text-white border-none animate-pulse">Ringing</Badge>;
        }
        if (status === 'answered' || status === 'in-progress') {
            return <Badge className="bg-indigo-500 hover:bg-indigo-600 text-white border-none animate-pulse">In Call</Badge>;
        }
    }

    return <Badge variant="secondary">In Progress</Badge>;
};

export function WorkflowRunsTable({
    runs,
    loading,
    error,
    currentPage,
    totalPages,
    totalCount,
    onPageChange,
    availableAttributes,
    activeFilters,
    onFiltersChange,
    onApplyFilters,
    onClearFilters,
    isExecutingFilters,
    hasAppliedFilters = false,
    sortBy,
    sortOrder = 'desc',
    onSort,
    workflowId,
    onReload,
    title = "Workflow Run History",
    subtitle,
    showFilters = true,
    emptyMessage = "No workflow runs found",
}: WorkflowRunsTableProps) {
    const [selectedRowId, setSelectedRowId] = useState<number | null>(null);
    // Track manually overridden intents: { [runId]: intent }
    const [editIntentMap, setEditIntentMap] = useState<Record<number, string>>({});
    // Track which row's edit dropdown is open
    const [editingRunId, setEditingRunId] = useState<number | null>(null);
    const [savingRunId, setSavingRunId] = useState<number | null>(null);

    // Media preview dialog
    const mediaPreview = MediaPreviewDialog();

    const formatDate = (dateString: string) => new Date(dateString).toLocaleString();

    const handleRowClick = (runId: number) => {
        window.open(`/workflow/${workflowId}/run/${runId}`, '_blank');
    };

    const auth = useAuth();

    const handleSaveIntent = async (run: WorkflowRunResponseSchema, newIntent: string) => {
        setSavingRunId(run.id);
        setEditingRunId(null);
        setEditIntentMap(prev => ({ ...prev, [run.id]: newIntent }));
        toast.success(`Intent updated to ${newIntent}`);
        try {
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

    return (
        <div className="space-y-6">
            {/* Title and Filters */}
            {showFilters && (
                <div className="mb-6">
                    <h1 className="text-2xl font-bold mb-4">{title}</h1>
                    <FilterBuilder
                        availableAttributes={availableAttributes}
                        activeFilters={activeFilters}
                        onFiltersChange={onFiltersChange}
                        onApplyFilters={onApplyFilters}
                        onClearFilters={onClearFilters}
                        isExecuting={isExecutingFilters}
                        hasAppliedFilters={hasAppliedFilters}
                    />
                </div>
            )}

            {/* Loading State */}
            {loading ? (
                <div className="flex justify-center">
                    <div className="animate-pulse">Loading workflow runs...</div>
                </div>
            ) : error ? (
                <div className="bg-destructive/10 border border-destructive/30 text-destructive px-4 py-3 rounded">
                    {error}
                </div>
            ) : runs.length === 0 ? (
                <div className="text-center py-8">
                    <p className="text-muted-foreground">{emptyMessage}</p>
                </div>
            ) : (
                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle>Workflow Runs</CardTitle>
                                <CardDescription>
                                    {subtitle || `Showing ${runs.length} of ${totalCount} total runs`}
                                </CardDescription>
                            </div>
                            {onReload && (
                                <Button
                                    variant="outline"
                                    size="icon"
                                    onClick={onReload}
                                    disabled={loading}
                                    title="Reload"
                                >
                                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                                </Button>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
                            <Table>
                                <TableHeader>
                                    <TableRow className="bg-muted/50">
                                        <TableHead className="font-semibold">ID</TableHead>
                                        <TableHead className="font-semibold">Status</TableHead>
                                        <TableHead className="font-semibold">Created At</TableHead>
                                        <TableHead className="font-semibold">Call Type</TableHead>
                                        <TableHead
                                            className="font-semibold cursor-pointer hover:bg-muted/50 select-none"
                                            onClick={() => onSort?.('duration')}
                                        >
                                            <div className="flex items-center gap-1">
                                                Duration
                                                {sortBy === 'duration' ? (
                                                    sortOrder === 'asc' ? <ArrowUp className="h-4 w-4" /> : <ArrowDown className="h-4 w-4" />
                                                ) : (
                                                    <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
                                                )}
                                            </div>
                                        </TableHead>
                                        <TableHead className="font-semibold">Disposition</TableHead>
                                        <TableHead className="font-semibold">Intent</TableHead>
                                        <TableHead className="font-semibold">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {runs.map((run) => {
                                        const gc = run.gathered_context || {};
                                        const backendIntent = (run as any).user_intent;
                                        const explicitIntent = backendIntent || (gc.user_intent || gc.intent || gc.interest_level || gc.interest) as string | undefined;
                                        let detectedIntent = explicitIntent;
                                        if (!detectedIntent) {
                                            const disposition = (gc.mapped_call_disposition as string || '').toLowerCase();
                                            if (gc.user_qualified === true || disposition === 'user_qualified') {
                                                detectedIntent = 'Interested';
                                            } else if (gc.user_qualified === false || disposition === 'disqualified') {
                                                detectedIntent = 'Not Interested';
                                            } else if (['busy', 'no-answer', 'failed', 'canceled', 'cancelled', 'initialized'].includes(disposition)) {
                                                detectedIntent = 'Not Connected';
                                            } else {
                                                detectedIntent = 'Not Interested';
                                            }
                                        }

                                        return (
                                        <TableRow
                                            key={run.id}
                                            className={`cursor-pointer hover:bg-muted/50 ${selectedRowId === run.id ? "bg-primary/20 ring-1 ring-primary/50" : ""}`}
                                            onClick={() => handleRowClick(run.id)}
                                        >
                                            <TableCell className="font-mono text-sm">#{run.id}</TableCell>
                                            <TableCell>
                                                {getCallStatusBadge(run)}
                                            </TableCell>
                                            <TableCell className="text-sm">{formatDate(run.created_at)}</TableCell>
                                            <TableCell>
                                                <CallTypeCell mode={run.mode} callType={run.call_type} />
                                            </TableCell>
                                            <TableCell className="text-sm">
                                                {typeof run.cost_info?.call_duration_seconds === 'number'
                                                    ? `${run.cost_info.call_duration_seconds.toFixed(1)}s`
                                                    : "-"}
                                            </TableCell>
                                            <TableCell>
                                                {run.gathered_context?.mapped_call_disposition ? (
                                                    <Badge variant="default">
                                                        {run.gathered_context.mapped_call_disposition as string}
                                                    </Badge>
                                                ) : (
                                                    <span className="text-sm text-muted-foreground">-</span>
                                                )}
                                            </TableCell>
                                             <TableCell onClick={(e) => e.stopPropagation()}>
                                                 <div className="relative inline-block text-left">
                                                     {(() => {
                                                         const currentVal = editIntentMap[run.id] || detectedIntent || 'Not Interested';
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
                                            <TableCell>
                                                <div className="flex space-x-2" onClick={(e) => e.stopPropagation()}>
                                                    <MediaPreviewButton
                                                        recordingUrl={run.recording_url}
                                                        transcriptUrl={run.transcript_url}
                                                        runId={run.id}
                                                        onOpenPreview={mediaPreview.openPreview}
                                                        onSelect={setSelectedRowId}
                                                    />
                                                    <Button
                                                        variant="outline"
                                                        size="icon"
                                                        onClick={() => window.open(`/workflow/${workflowId}/run/${run.id}`, '_blank')}
                                                    >
                                                        <ExternalLink className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </div>

                        {/* Pagination */}
                        {totalPages > 1 && (
                            <div className="flex items-center justify-between mt-6">
                                <p className="text-sm text-muted-foreground">
                                    Page {currentPage} of {totalPages}
                                </p>
                                <div className="flex gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => onPageChange(currentPage - 1)}
                                        disabled={currentPage === 1}
                                    >
                                        <ChevronLeft className="h-4 w-4" />
                                        Previous
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => onPageChange(currentPage + 1)}
                                        disabled={currentPage === totalPages}
                                    >
                                        Next
                                        <ChevronRight className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Media Preview Dialog */}
            {mediaPreview.dialog}
        </div>
    );
}
