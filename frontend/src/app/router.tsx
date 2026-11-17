import { createBrowserRouter, Navigate } from "react-router";
import { AssignPage } from "../features/assign/AssignPage";
import { AppShell } from "./AppShell";
import { ApplicantsPage, CoursesPage, EligibilityPage } from "./LegacyPages";

export const router = createBrowserRouter([
    {
        path: "/",
        element: <AppShell />,
        children: [
            { index: true, element: <Navigate to="/assign" replace /> },
            { path: "assign", element: <AssignPage /> },
            { path: "courses", element: <CoursesPage /> },
            { path: "applicants", element: <ApplicantsPage /> },
            { path: "eligibility", element: <EligibilityPage /> },
            { path: "*", element: <Navigate to="/assign" replace /> },
        ],
    },
]);
