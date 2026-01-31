import React from 'react';
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DateRange } from "react-day-picker";
import { CalendarIcon, LayoutGrid, List, Map as MapIcon, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { format } from "date-fns";
import { useTheme } from "@/components/theme-provider";

interface DashboardHeaderProps {
    date: DateRange | undefined;
    setDate: (date: DateRange | undefined) => void;
    viewMode: 'list' | 'map' | 'grid';
    setViewMode: (mode: 'list' | 'map' | 'grid') => void;
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({
    date,
    setDate,
    viewMode,
    setViewMode
}) => {
    const { theme, setTheme } = useTheme();

    return (
        <div className="flex flex-col space-y-4 md:flex-row md:items-center md:justify-between space-y-0 pb-6 sticky top-0 z-10 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 py-4 border-b">

            {/* Metrics & Title */}
            <div>
                <h2 className="text-3xl font-bold tracking-tight">Network Overview</h2>
                <p className="text-muted-foreground">Monitor performance across all locations.</p>
            </div>

            {/* Filters & Controls */}
            <div className="flex flex-wrap items-center gap-2">

                {/* Status Filter */}
                <Select defaultValue="all">
                    <SelectTrigger className="w-[140px]">
                        <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Salons</SelectItem>
                        <SelectItem value="active">Active Only</SelectItem>
                        <SelectItem value="problem">Problems</SelectItem>
                        <SelectItem value="offline">Offline</SelectItem>
                    </SelectContent>
                </Select>

                {/* Region Filter */}
                <Select defaultValue="all_regions">
                    <SelectTrigger className="w-[140px]">
                        <SelectValue placeholder="Region" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all_regions">All Regions</SelectItem>
                        <SelectItem value="spb">St. Petersburg</SelectItem>
                        <SelectItem value="msk">Moscow</SelectItem>
                    </SelectContent>
                </Select>


                {/* Date Picker */}
                <Popover>
                    <PopoverTrigger asChild>
                        <Button
                            id="date"
                            variant={"outline"}
                            className={cn(
                                "w-[240px] justify-start text-left font-normal",
                                !date && "text-muted-foreground"
                            )}
                        >
                            <CalendarIcon className="mr-2 h-4 w-4" />
                            {date?.from ? (
                                date.to ? (
                                    <>
                                        {format(date.from, "LLL dd, y")} -{" "}
                                        {format(date.to, "LLL dd, y")}
                                    </>
                                ) : (
                                    format(date.from, "LLL dd, y")
                                )
                            ) : (
                                <span>Pick a date</span>
                            )}
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="end">
                        <Calendar
                            initialFocus
                            mode="range"
                            defaultMonth={date?.from}
                            selected={date}
                            onSelect={setDate}
                            numberOfMonths={2}
                        />
                    </PopoverContent>
                </Popover>

                {/* View Mode Toggles */}
                <div className="flex items-center border rounded-md p-1 bg-muted/20">
                    <Button
                        variant={viewMode === 'list' ? 'secondary' : 'ghost'}
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => setViewMode('list')}
                    >
                        <List className="h-4 w-4" />
                    </Button>
                    <Button
                        variant={viewMode === 'map' ? 'secondary' : 'ghost'}
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => setViewMode('map')}
                    >
                        <MapIcon className="h-4 w-4" />
                    </Button>
                    <Button
                        variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => setViewMode('grid')}
                    >
                        <LayoutGrid className="h-4 w-4" />
                    </Button>
                </div>

                {/* Theme Toggle */}
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setTheme(theme === "light" ? "dark" : "light")}
                >
                    <Sun className="h-[1.2rem] w-[1.2rem] rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
                    <Moon className="absolute h-[1.2rem] w-[1.2rem] rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
                    <span className="sr-only">Toggle theme</span>
                </Button>

            </div>
        </div>
    );
};
