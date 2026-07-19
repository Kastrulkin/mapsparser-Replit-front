
import { newAuth } from "@/lib/auth_new";

type ApiOptions = {
    params?: Record<string, string | number | boolean | null | undefined>;
    headers?: Record<string, string>;
    body?: unknown;
};

const buildUrl = (url: string, params?: ApiOptions["params"]) => {
    if (!params) {
        return url;
    }

    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== null && value !== undefined && String(value).length > 0) {
            searchParams.set(key, String(value));
        }
    });

    const query = searchParams.toString();
    if (!query) {
        return url;
    }

    return `${url}${url.includes("?") ? "&" : "?"}${query}`;
};

// Axios-like wrapper around newAuth.makeRequest
export const api = {
    get: async (url: string, options: ApiOptions = {}) => {
        const data = await newAuth.makeRequest(buildUrl(url, options.params), {
            method: 'GET',
            headers: options.headers,
        });
        return { data };
    },
    post: async (url: string, body: any = {}, options: ApiOptions = {}) => {
        const data = await newAuth.makeRequest(url, {
            method: 'POST',
            headers: options.headers,
            body: JSON.stringify(body)
        });
        return { data };
    },
    put: async (url: string, body: any, options: ApiOptions = {}) => {
        const data = await newAuth.makeRequest(url, {
            method: 'PUT',
            headers: options.headers,
            body: JSON.stringify(body)
        });
        return { data };
    },
    delete: async (url: string, options: ApiOptions = {}) => {
        const data = await newAuth.makeRequest(buildUrl(url, options.params), {
            method: 'DELETE',
            headers: options.headers,
            body: options.body === undefined ? undefined : JSON.stringify(options.body),
        });
        return { data };
    }
};
