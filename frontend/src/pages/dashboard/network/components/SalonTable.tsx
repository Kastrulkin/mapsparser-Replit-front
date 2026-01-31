import React, { useState } from 'react';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    ArrowUpDown,
    MoreHorizontal,
    AlertTriangle,
    WifiOff,
    CheckCircle2,
    ChevronDown,
    ChevronRight,
    Search
} from "lucide-react";
import { SalonData, mockSalons } from '../data/mockData';
import { SalonMiniDashboard } from './SalonMiniDashboard';
import { Input } from "@/components/ui/input";

export const SalonTable: React.FC = () => {
    const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
    const [sortConfig, setSortConfig] = useState<{ key: keyof SalonData; direction: 'asc' | 'desc' } | null>(null);
    const [filter, setFilter] = useState("");

    const toggleRow = (id: string) => {
        const newExpanded = new Set(expandedRows);
        if (newExpanded.has(id)) {
            newExpanded.delete(id);
        } else {
            newExpanded.add(id);
        }
        setExpandedRows(newExpanded);
    };

    const handleSort = (key: keyof SalonData) => {
        let direction: 'asc' | 'desc' = 'asc';
        if (sortConfig && sortConfig.key === key && sortConfig.direction === 'asc') {
            direction = 'desc';
        }
        setSortConfig({ key, direction });
    };

    const sortedData = [...mockSalons].sort((a, b) => {
        if (!sortConfig) return 0;
        const aVal = a[sortConfig.key];
        const bVal = b[sortConfig.key];
        if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
    }).filter(s => s.name.toLowerCase().includes(filter.toLowerCase()));

    const getStatusBadge = (status: SalonData['status']) => {
        switch (status) {
            case 'active':
                return <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 border-emerald-500/20"><CheckCircle2 className="w-3 h-3 mr-1" /> Active</Badge>;
            case 'problem':
                return <Badge variant="destructive" className="bg-red-500/10 text-red-600 hover:bg-red-500/20 border-red-500/20"><AlertTriangle className="w-3 h-3 mr-1" /> Attention</Badge>;
            case 'offline':
                return <Badge variant="secondary" className="text-muted-foreground"><WifiOff className="w-3 h-3 mr-1" /> Offline</Badge>;
        }
    };

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h3 className="text-xl font-semibold tracking-tight">Detailed Performance</h3>
                <div className="relative w-[250px]">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search salons..."
                        className="pl-8"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                    />
                </div>
            </div>

            <div className="rounded-md border">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-[50px]"></TableHead>
                            <TableHead className="w-[250px]">
                                <Button variant="ghost" className="-ml-4 h-8 text-xs font-semibold" onClick={() => handleSort('name')}>
                                    Salon Name <ArrowUpDown className="ml-2 h-3 w-3" />
                                </Button>
                            </TableHead>
                            <TableHead>
                                <Button variant="ghost" className="-ml-4 h-8 text-xs font-semibold" onClick={() => handleSort('status')}>
                                    Status <ArrowUpDown className="ml-2 h-3 w-3" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-right">
                                <Button variant="ghost" className="-mr-4 h-8 text-xs font-semibold" onClick={() => handleSort('rating')}>
                                    Rating <ArrowUpDown className="ml-2 h-3 w-3" />
                                </Button>
                            </TableHead>
                            <TableHead className="text-right">Reviews</TableHead>
                            <TableHead className="text-right">% Negative</TableHead>
                            <TableHead className="w-[50px]"></TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {sortedData.map((salon) => (
                            <React.Fragment key={salon.id}>
                                <TableRow
                                    className={`cursor-pointer group ${expandedRows.has(salon.id) ? "bg-muted/50 border-b-0" : ""}`}
                                    onClick={() => toggleRow(salon.id)}
                                >
                                    <TableCell>
                                        {expandedRows.has(salon.id) ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground" />}
                                    </TableCell>
                                    <TableCell className="font-medium">
                                        {salon.name}
                                        <div className="text-xs text-muted-foreground font-normal">{salon.address}</div>
                                    </TableCell>
                                    <TableCell>{getStatusBadge(salon.status)}</TableCell>
                                    <TableCell className="text-right font-bold">
                                        {salon.rating} <span className="text-muted-foreground text-xs font-normal">/ 5</span>
                                    </TableCell>
                                    <TableCell className="text-right">{salon.reviews}</TableCell>
                                    <TableCell className="text-right">
                                        <span className={salon.negativePercent > 15 ? "text-red-600 font-bold" : salon.negativePercent > 5 ? "text-yellow-600" : "text-emerald-600"}>
                                            {salon.negativePercent}%
                                        </span>
                                    </TableCell>
                                    <TableCell>
                                        <Button variant="ghost" size="icon" className="h-8 w-8">
                                            <MoreHorizontal className="h-4 w-4" />
                                        </Button>
                                    </TableCell>
                                </TableRow>
                                {expandedRows.has(salon.id) && (
                                    <TableRow className="bg-muted/50 border-t-0 hover:bg-muted/50">
                                        <TableCell colSpan={7} className="p-4 pt-0">
                                            <SalonMiniDashboard salon={salon} />
                                        </TableCell>
                                    </TableRow>
                                )}
                            </React.Fragment>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
};
