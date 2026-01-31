import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SalonData } from '../data/mockData';
import { AlertCircle, ArrowRight, ExternalLink, MapPin } from 'lucide-react';
import { Badge } from "@/components/ui/badge";

interface SalonMiniDashboardProps {
    salon: SalonData;
}

export const SalonMiniDashboard: React.FC<SalonMiniDashboardProps> = ({ salon }) => {
    return (
        <div className="p-4 bg-muted/30 rounded-lg border space-y-4 animate-in fade-in zoom-in-95 duration-200">

            <div className="flex flex-col md:flex-row gap-6">
                {/* Left: Info & Actions */}
                <div className="w-full md:w-1/3 space-y-4">
                    <div>
                        <h4 className="font-semibold text-sm mb-1">Location Details</h4>
                        <div className="flex items-start text-sm text-muted-foreground">
                            <MapPin className="h-4 w-4 mr-1 mt-0.5 shrink-0" />
                            <span>{salon.address}</span>
                        </div>
                    </div>

                    <div className="flex gap-2">
                        <Button size="sm" variant="outline" className="w-full justify-start">
                            <ExternalLink className="mr-2 h-3 w-3" />
                            Open Dashboard
                        </Button>
                        <Button size="sm" variant="destructive" className="w-auto px-2">
                            <AlertCircle className="h-3 w-3" />
                        </Button>
                    </div>
                </div>

                {/* Right: Recent Reviews */}
                <div className="w-full md:w-2/3">
                    <h4 className="font-semibold text-sm mb-3">Recent Feedback</h4>
                    <div className="grid gap-3">
                        {salon.recentReviews.length > 0 ? (
                            salon.recentReviews.map((review) => (
                                <div key={review.id} className="bg-background border rounded p-3 text-sm shadow-sm">
                                    <div className="flex justify-between items-start mb-1">
                                        <div className="flex items-center gap-2">
                                            <span className="font-medium">{review.author}</span>
                                            <div className="flex text-yellow-500 text-xs">
                                                {[...Array(5)].map((_, i) => (
                                                    <span key={i} className={i < review.rating ? "opacity-100" : "opacity-20"}>★</span>
                                                ))}
                                            </div>
                                        </div>
                                        <span className="text-xs text-muted-foreground">{review.date}</span>
                                    </div>
                                    <p className="text-muted-foreground line-clamp-2">{review.text}</p>
                                    <div className="mt-2 text-xs">
                                        <Badge variant={review.sentiment === 'positive' ? 'outline' : review.sentiment === 'negative' ? 'destructive' : 'secondary'} className="text-[10px] h-5 px-1.5 font-normal">
                                            {review.sentiment}
                                        </Badge>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="text-sm text-muted-foreground italic p-2">
                                No recent reviews found.
                            </div>
                        )}
                    </div>
                </div>
            </div>

        </div>
    );
};
