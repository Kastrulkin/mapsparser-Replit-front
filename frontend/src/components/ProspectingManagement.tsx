
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Badge } from "./ui/badge";
import { Loader2, Search, Save, MapPin, Phone, Globe, Star, Users } from "lucide-react";
import { api } from "@/services/api";

type Lead = {
    id?: string;
    name: string;
    address?: string;
    phone?: string;
    website?: string;
    rating?: number;
    reviews_count?: number;
    source_url?: string;
    google_id?: string;
    category?: string;
    location?: any;
    status: string;
};

export const ProspectingManagement: React.FC = () => {
    const [query, setQuery] = useState('');
    const [location, setLocation] = useState('');
    const [limit, setLimit] = useState(20);
    const [results, setResults] = useState<Lead[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState<Record<string, boolean>>({});
    const [savedLeads, setSavedLeads] = useState<Lead[]>([]);
    const [loadingLeads, setLoadingLeads] = useState(false);

    useEffect(() => {
        fetchSavedLeads();
    }, []);

    const fetchSavedLeads = async () => {
        setLoadingLeads(true);
        try {
            const response = await api.get('/admin/prospecting/leads');
            setSavedLeads(response.data.leads || []);
        } catch (error) {
            console.error('Error fetching leads:', error);
        } finally {
            setLoadingLeads(false);
        }
    };

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query || !location) return;

        setLoading(true);
        try {
            const response = await api.post('/admin/prospecting/search', {
                query,
                location,
                limit: Number(limit)
            });
            console.log("Search results:", response.data);
            // Ensure results have status 'new' for display
            const newResults = (response.data.results || []).map((r: any) => ({ ...r, status: 'new' }));
            setResults(newResults);
        } catch (error) {
            console.error('Error searching:', error);
            alert('Error searching. Check console.');
        } finally {
            setLoading(false);
        }
    };

    const saveLead = async (lead: Lead) => {
        const key = lead.google_id || lead.name;
        setSaving(prev => ({ ...prev, [key]: true }));
        try {
            await api.post('/admin/prospecting/save', { lead });
            fetchSavedLeads(); // Refresh list
        } catch (error) {
            console.error('Error saving lead:', error);
        } finally {
            setSaving(prev => ({ ...prev, [key]: false }));
        }
    };

    const updateStatus = async (leadId: string, status: string) => {
        try {
            await api.post(`/admin/prospecting/lead/${leadId}/status`, { status });
            fetchSavedLeads();
        } catch (error) {
            console.error('Error updating status:', error);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Prospecting</h2>
                    <p className="text-muted-foreground">Find and manage potential clients using Apify.</p>
                </div>
            </div>

            <Tabs defaultValue="search" className="w-full">
                <TabsList>
                    <TabsTrigger value="search">Search</TabsTrigger>
                    <TabsTrigger value="leads">Saved Leads ({savedLeads.length})</TabsTrigger>
                </TabsList>

                <TabsContent value="search" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>Search Parameters</CardTitle>
                            <CardDescription>Search for businesses on Google Maps via Apify</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleSearch} className="flex gap-4 items-end">
                                <div className="grid w-full max-w-sm items-center gap-1.5">
                                    <label htmlFor="query">Keywords</label>
                                    <Input
                                        type="text"
                                        id="query"
                                        placeholder="e.g. Hair Salon"
                                        value={query}
                                        onChange={(e) => setQuery(e.target.value)}
                                        required
                                    />
                                </div>
                                <div className="grid w-full max-w-sm items-center gap-1.5">
                                    <label htmlFor="location">Location</label>
                                    <Input
                                        type="text"
                                        id="location"
                                        placeholder="e.g. Moscow, Russia"
                                        value={location}
                                        onChange={(e) => setLocation(e.target.value)}
                                        required
                                    />
                                </div>
                                <div className="grid w-24 items-center gap-1.5">
                                    <label htmlFor="limit">Limit</label>
                                    <Input
                                        type="number"
                                        id="limit"
                                        value={limit}
                                        onChange={(e) => setLimit(Number(e.target.value))}
                                        min={1}
                                        max={200}
                                    />
                                </div>
                                <Button type="submit" disabled={loading}>
                                    {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                    Search
                                </Button>
                            </form>
                        </CardContent>
                    </Card>

                    {results.length > 0 && (
                        <Card>
                            <CardHeader>
                                <CardTitle>Results ({results.length})</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Name</TableHead>
                                            <TableHead>Address</TableHead>
                                            <TableHead>Contacts</TableHead>
                                            <TableHead>Rating</TableHead>
                                            <TableHead>Action</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {results.map((r, i) => {
                                            // Check if already saved
                                            const isSaved = Array.isArray(savedLeads) && savedLeads.some(sl => sl.google_id === r.google_id);
                                            const key = r.google_id || r.name;

                                            return (
                                                <TableRow key={i}>
                                                    <TableCell className="font-medium">
                                                        <div>{r.name}</div>
                                                        {r.category && <span className="text-xs text-muted-foreground">{r.category}</span>}
                                                    </TableCell>
                                                    <TableCell className="max-w-[200px] truncate" title={r.address}>
                                                        <div className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {r.address}</div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <div className="flex flex-col gap-1 text-sm">
                                                            {r.phone && <span className="flex items-center gap-1"><Phone className="h-3 w-3" /> {r.phone}</span>}
                                                            {r.website && <span className="flex items-center gap-1"><Globe className="h-3 w-3" /> <a href={r.website} target="_blank" rel="noreferrer" className="underline truncate max-w-[150px]">{r.website}</a></span>}
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        {r.rating && (
                                                            <div className="flex items-center gap-1">
                                                                <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                                                                {r.rating}
                                                                <span className="text-muted-foreground">({r.reviews_count})</span>
                                                            </div>
                                                        )}
                                                    </TableCell>
                                                    <TableCell>
                                                        <Button
                                                            size="sm"
                                                            variant={isSaved ? "secondary" : "default"}
                                                            onClick={() => saveLead(r)}
                                                            disabled={isSaved || saving[key]}
                                                        >
                                                            {saving[key] && <Loader2 className="mr-2 h-3 w-3 animate-spin" />}
                                                            {isSaved ? "Saved" : "Save"}
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                <TabsContent value="leads">
                    <Card>
                        <CardHeader>
                            <CardTitle>Saved Leads</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {loadingLeads ? (
                                <div className="flex justify-center p-8"><Loader2 className="h-8 w-8 animate-spin" /></div>
                            ) : (
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Name</TableHead>
                                            <TableHead>Contact Info</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead>Added</TableHead>
                                            <TableHead>Action</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {savedLeads.map((lead) => (
                                            <TableRow key={lead.id}>
                                                <TableCell className="font-medium">
                                                    <div>{lead.name}</div>
                                                    <div className="text-xs text-muted-foreground">{lead.category}</div>
                                                    {lead.source_url && <a href={lead.source_url} target="_blank" rel="noreferrer" className="text-xs text-blue-500 underline">Maps Link</a>}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex flex-col gap-1 text-sm">
                                                        {lead.phone && <span className="flex items-center gap-1"><Phone className="h-3 w-3" /> {lead.phone}</span>}
                                                        {lead.website && <span className="flex items-center gap-1"><Globe className="h-3 w-3" /> <a href={lead.website} target="_blank" rel="noreferrer" className="underline truncate max-w-[150px]">{lead.website}</a></span>}
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <select
                                                        className="bg-transparent border rounded p-1 text-sm"
                                                        value={lead.status}
                                                        onChange={(e) => lead.id && updateStatus(lead.id, e.target.value)}
                                                    >
                                                        <option value="new">New</option>
                                                        <option value="contacted">Contacted</option>
                                                        <option value="qualified">Qualified</option>
                                                        <option value="converted">Converted</option>
                                                        <option value="rejected">Rejected</option>
                                                    </select>
                                                </TableCell>
                                                <TableCell className="text-muted-foreground text-xs">
                                                    {/* We don't have created_at in type yet but it comes from DB */}
                                                    {/* @ts-ignore */}
                                                    {lead.created_at ? new Date(lead.created_at).toLocaleDateString() : '-'}
                                                </TableCell>
                                                <TableCell>
                                                    {/* Actions like Edit, Delete could go here */}
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                        {savedLeads.length === 0 && (
                                            <TableRow>
                                                <TableCell colSpan={5} className="text-center py-4">No leads saved yet.</TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default ProspectingManagement;
