import { createBrowserRouter, Navigate } from "react-router";
import { AssignPage } from "../features/assign/AssignPage";
import { DataPage } from "../features/data/DataPage";
import { StartPage } from "../features/onboarding/StartPage";
import { WelcomePage } from "../features/onboarding/WelcomePage";
import { RulesPage } from "../features/rules/RulesPage";
import { AppShell } from "./AppShell";
import { ApplicantsPage, CoursesPage, EligibilityPage } from "./LegacyPages";

export const router = createBrowserRouter([
    { path: "/welcome", element: <WelcomePage /> },
    {
        path: "/",
        element: <AppShell />,
        children: [
            { index: true, element: <Navigate to="/start" replace /> },
            { path: "start", element: <StartPage /> },
            { path: "rules", element: <RulesPage /> },
            { path: "courses", element: <CoursesPage /> },
            { path: "applicants", element: <ApplicantsPage /> },
            { path: "assign", element: <AssignPage /> },
            { path: "data", element: <DataPage /> },
            { path: "eligibility", element: <EligibilityPage /> },
            { path: "*", element: <Navigate to="/start" replace /> },
        ],
    },
]);
