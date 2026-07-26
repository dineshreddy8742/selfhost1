"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, ExternalLink, RefreshCw } from "lucide-react";
import { useState } from "react";

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

    // Media preview dialog
    const mediaPreview = MediaPreviewDialog();

    const formatDate = (dateString: string) => new Date(dateString).toLocaleString();

    const handleRowClick = (runId: number) => {
        window.open(`/workflow/${workflowId}/run/${runId}`, '_blank');
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
                                        const explicitIntent = (gc.user_intent || gc.intent || gc.interest_level || gc.interest) as string | undefined;
                                        let detectedIntent = explicitIntent;
                                        if (!detectedIntent) {
                                            if (gc.user_qualified === true || gc.mapped_call_disposition === 'user_qualified') {
                                                detectedIntent = 'Interested';
                                            } else if (gc.user_qualified === false || gc.mapped_call_disposition === 'disqualified') {
                                                detectedIntent = 'Not Interested';
                                            } else if (['busy', 'no-answer', 'failed', 'canceled'].includes((gc.mapped_call_disposition as string || '').toLowerCase())) {
                                                detectedIntent = 'Not Connected';
                                            } else if (run.is_completed) {
                                                detectedIntent = 'Neutral';
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
                                            <TableCell>
                                                {detectedIntent === 'Interested' ? (
                                                    <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/25">
                                                        Interested
                                                    </Badge>
                                                ) : detectedIntent === 'Not Interested' ? (
                                                    <Badge className="bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30 hover:bg-rose-500/25">
                                                        Not Interested
                                                    </Badge>
                                                ) : detectedIntent === 'Neutral' ? (
                                                    <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 hover:bg-amber-500/25">
                                                        Neutral
                                                    </Badge>
                                                ) : detectedIntent ? (
                                                    <Badge variant="outline" className="text-muted-foreground">
                                                        {detectedIntent}
                                                    </Badge>
                                                ) : (
                                                    <span className="text-sm text-muted-foreground">-</span>
                                                )}
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
                                    ))}
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
