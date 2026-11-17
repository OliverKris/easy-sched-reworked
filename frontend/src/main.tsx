import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import "./index.css";
import { router } from "./app/router";
import { WorkspaceProvider } from "./app/workspace";

const queryClient = new QueryClient({
    defaultOptions: {
        queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 30_000 },
    },
});

createRoot(document.getElementById("root")!).render(
    <StrictMode>
        <QueryClientProvider client={queryClient}>
            <WorkspaceProvider>
                <RouterProvider router={router} />
            </WorkspaceProvider>
        </QueryClientProvider>
    </StrictMode>,
);
