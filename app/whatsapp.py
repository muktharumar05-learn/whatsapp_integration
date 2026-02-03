from fastapi.templating import Jinja2Templates
import logging
import asyncio
from fastapi import (
    FastAPI,
    Form,

    Request,
    BackgroundTasks,
    status,
)
from fastapi.responses import (
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
)
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from twilio.twiml.messaging_response import MessagingResponse
from langchain_core.messages import HumanMessage, AIMessage
from agent.react_agent import agent, monitor_active_leads
from client.twilio_client import TWILIO_WHATSAPP_NUMBER
from contextlib import asynccontextmanager
from database.initdb import init_pool, init_db, close_pool
from service.dashboard import load_template_and_inject_rows
from database.retrieve_data import fetch_all_leads
from service.signup import register_new_customer
from service.leads import LeadService
from service.signin import authenticate_user, login_required


# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

templates = Jinja2Templates(directory="html_templates")


# -------------------------------------------------
# App Lifespan
# -------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Starting lifespan startup...")
    await init_pool()
    await init_db()
    monitor_task = asyncio.create_task(monitor_active_leads())
    logging.info("Finished lifespan startup.")
    yield
    logging.info("Starting lifespan shutdown...")
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        logging.info("Monitor task stopped.")
    await close_pool()
    logging.info("Finished lifespan shutdown.")


# -------------------------------------------------
# FastAPI App
# -------------------------------------------------
app = FastAPI(lifespan=lifespan)


# -------------------------------------------------
# Middleware
# -------------------------------------------------

# 🔐 Session Middleware (LOGIN STATE)
app.add_middleware(
    SessionMiddleware,
    secret_key="SUPER_SECRET_CHANGE_THIS",   # ⚠️ use env var in prod
    session_cookie="session",
    max_age=60 * 60,                         # 1 hour
    same_site="lax",
    https_only=False                         # True in production
)

# 🌍 CORS Middleware (needed only if JS frontend exists)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------
# Helpers
# -------------------------------------------------
async def get_or_create_state(
    username: str,
    user_mobile_number: str,
    client_mobile_number: str,
):
    return {
        "messages": [],
        "user_mobile_number": user_mobile_number,
        "client_mobile_number": client_mobile_number,
        "username": username,
    }


# -------------------------------------------------
# WhatsApp Routes
# -------------------------------------------------
@app.get("/go")
def redirect_to_whatsapp():
    number = TWILIO_WHATSAPP_NUMBER.replace("whatsapp:", "").replace("+", "")
    return RedirectResponse(f"https://wa.me/{number}")


@app.post("/whatsapp")
async def whatsapp_webhook(
    To: str = Form(...),
    From: str = Form(...),
    Body: str = Form(...),
    ProfileName: str = Form(None),
):
    business_number = To.replace("whatsapp:", "")
    user_number = From.replace("whatsapp:", "")
    username = ProfileName or "User"
    user_message = Body.strip()

    try:
        await LeadService.capture_initial_contact(
            client=business_number,
            user_mobile=user_number,
            username=username,
        )
    except Exception as e:
        logging.error(f"Lead capture failed: {e}")

    try:
        state = await get_or_create_state(username, user_number, business_number)

        state["messages"].append(
            HumanMessage(
                content=f"[User: {username} | Mobile: {user_number}] {user_message}"
            )
        )

        if hasattr(agent, "ainvoke"):
            result = await agent.ainvoke(state)
        else:
            result = await asyncio.to_thread(agent.invoke, state)

        ai_reply = result["messages"][-1].content
        state["messages"].append(AIMessage(content=ai_reply))

        resp = MessagingResponse()
        resp.message(ai_reply)

        return PlainTextResponse(
            str(resp),
            media_type="application/xml",
        )

    except Exception as e:
        logging.error(f"WhatsApp webhook error: {e}", exc_info=True)
        resp = MessagingResponse()
        resp.message("Sorry, something went wrong.")
        return PlainTextResponse(str(resp), media_type="application/xml")


# -------------------------------------------------
# Website Routes
# -------------------------------------------------
@app.get("/home", response_class=HTMLResponse)
async def welcome_page(request: Request):
    return templates.TemplateResponse(
        "landingpage.html",
        {"request": request},
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request},
    )


@app.post("/login")
async def login_route(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    user = await authenticate_user(username, password)

    request.session["user"] = {
        "user_id": user["id"],
        "username": user["username"],
    }

    return RedirectResponse(
        url="/login/dashboard",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse(
        "signup.html",
        {"request": request},
    )


@app.post("/signup")
async def handle_signup(
    background_tasks: BackgroundTasks,
    phone: str = Form(...),
    password: str = Form(...),
    url: str = Form(...),
    location: str = Form(...),
):
    try:
        await register_new_customer(
            phone,
            password,
            url,
            location,
            background_tasks,
        )
    except Exception as e:
        logging.error(f"Signup error: {e}")

    return HTMLResponse(
        content="<h1>Success!</h1><a href='/login'>Login</a>"
    )


@app.get("/login/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    # 1. Check Auth
    auth_redirect = login_required(request)
    if auth_redirect:
        return auth_redirect

    # 2. If we get here, the user IS logged in.
    # You can access their data from the session:
    user_data = request.session.get("user")
    username = user_data.get("username")

    # 3. Fetch data for the dashboard
    logging.info(f"Fetching dashboard for {username}...")
    leads = await fetch_all_leads(str(username))
    print(leads)

    # 4. Render the page
    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request, 
            "leads": leads, 
            "username": username
        }
    )


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(
        url="/login",
        status_code=status.HTTP_303_SEE_OTHER,
    )
