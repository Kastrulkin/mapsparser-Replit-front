
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

// Utility for merging tailwind classes
export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

// Pro UI Design Tokens
export const DESIGN_TOKENS = {
    // Glassmorphism variants
    glass: {
        default: "bg-white/70 backdrop-blur-md border border-white/20 shadow-xl",
        dark: "bg-black/70 backdrop-blur-md border border-white/10 shadow-xl",
        hover: "hover:bg-white/80 transition-all duration-300",
    },
    // Gradients for special elements
    gradients: {
        primary: "bg-gradient-to-br from-blue-600 via-indigo-500 to-purple-600",
        gold: "bg-gradient-to-br from-amber-400 via-orange-500 to-yellow-500",
        success: "bg-gradient-to-br from-emerald-400 via-green-500 to-teal-500",
    },
    // Animation durations
    motion: {
        fast: 0.15,
        normal: 0.3,
        slow: 0.5,
    },
};
