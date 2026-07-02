from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from tools.applicant_parser import load_applications
from tools.processed_parser import load_section_groups

groups = []
applications = []

# Runs before the app starts
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Mount static files (CSS, JS, etc.)
    app.mount("/static", StaticFiles(directory="static"), name="static")

    global groups, applications
    groups       = load_section_groups("data/processed_courses.json")
    applications = load_applications("data/applicants.json")
    yield


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


@app.get("/courses")
async def courses(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="pages/courses.html",      # only render the page-level template
        context={"request": request, "groups": groups}
    )

