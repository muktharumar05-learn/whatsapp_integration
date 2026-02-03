from urllib import request
import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from service.signup import register_new_customer
from database.retrieve_data import fetch_all_leads
from service.dashboard import load_template_and_inject_rows
from service.security import verify_password

app = FastAPI()

# Setup templates directory for your HTML files
templates = Jinja2Templates(directory=r"templates")

@app.get("/", response_class=HTMLResponse)
async def welcome_page(request: Request):
    """Serves the Landing Page Welcome Card."""
    return templates.TemplateResponse("landingpage.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Route for the Login button."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login_user(username: str, password: str):
    # # 1️⃣ Fetch user from DB
    # user = await fetch_user_by_username(username)

    # # 2️⃣ User not found
    # if not user:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail="User not found"
    #     )

    # # 3️⃣ Password mismatch
    # if not verify_password(password, user["hashed_password"]):
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Invalid password"
    #     )

    # 4️⃣ Success
    leads = await fetch_all_leads()
    html_content = load_template_and_inject_rows(leads)
    return templates.TemplateResponse("dashboard.html", {"request": request, "html_content": html_content})


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Route for the Signup button."""
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
async def handle_signup(
    phone: str = Form(...),
    password: str = Form(...),
    url: str = Form(...),
    location: str = Form(...)
):
    """Handles the form submission."""
    # Logic to save to your database would go here
    print(f"New Signup: {phone}, {url}, {location}")
    
    # Call the service layer function to register the customer
    try:
        result = await register_new_customer(phone, password, url, location)
        print(f"Registration result: {result}")
    except Exception as e:
        print(f"Error during registration: {e}")

    # For now, redirect back to home or a success page
    return HTMLResponse(content=f"<h1>Success!</h1><p>Account created for {phone}. <a href='/'>Go Home</a></p>")


# Dashboard
@app.get("/login/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    leads = await fetch_all_leads()
    html_content = load_template_and_inject_rows(leads)
    return templates.TemplateResponse("dashboard.html", {"request": request, "html_content": html_content})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
    
    