TO EXECUTE ME:

UPDATE YOUR GROQ API KEY AND TWILIO KEYS IN CONFIG.YAML 

HAVE DOCKER INSTALLED LOCALLY AND RUN: 
-docker build -t app.whatsapp .

-docker-compose up
-[If cached] 
-docker-compose down --volumes --remove-orphans
-docker-compose up --build

OPEN ANOTHER TERMINAL AND RUN: 
-ngrok http 8000
-Update the 'Forwarding' URL IN TWILIO SANDBOX POST URL