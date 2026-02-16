------------Welcome to StarryPlanner-------------
What am I?
I am a tool to help you plan your day, by saying what you want to do
- Natural language processing with openai's nano model
- No need to open your calendar webpage anymore

How does it work?
Just type what you want to schedule in plain English, like
"Lunch with Alice tomorrow 1-2pm at campus" and I will create
the event on your Google Calendar automatically.
- Understands dates, times, and recurring events
- Shows a preview before adding anything to your calendar
- Supports sign-in and sign-out from the Settings menu

How to run?
For development: python app.py
For desktop .exe: python build.py, then share the dist/AIScheduler folder
- Place .env and google_client_secret.json(Google Oauth for Calendar API calls) next to the .exe
- Your OpenAI API key goes in the .env file
- Google credentials are set up through the Settings sign-in flow

