
import { newAuth } from "@/lib/auth_new";

// Axios-like wrapper around newAuth.makeRequest
export const api = {
    get: async (url: string) => {
        const data = await newAuth.makeRequest(url, { method: 'GET' });
        return { data };
    },
    post: async (url: string, body: any) => {
        const data = await newAuth.makeRequest(url, {
            method: 'POST',
            body: JSON.stringify(body)
        });
        return { data };
    },
    put: async (url: string, body: any) => {
        const data = await newAuth.makeRequest(url, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
        return { data };
    },
    delete: async (url: string) => {
        const data = await newAuth.makeRequest(url, { method: 'DELETE' });
        return { data };
    }
};
