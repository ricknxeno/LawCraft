from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
import google.generativeai as genai
import requests
import json
import base64
import os
from django.conf import settings

# Configure API keys
genai.configure(api_key=settings.GOOGLE_API_KEY)

# Generation settings for Gemini
generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

@ensure_csrf_cookie
def chat(request):
    return render(request, 'chat/index.html')

def text_to_speech(request):
    try:
        print("Received text-to-speech request")
        data = json.loads(request.body)
        text = data.get('text', '')
        
        if not text:
            return JsonResponse({"error": "No text provided"}, status=400)
            
        if not settings.ELEVEN_LABS_API_KEY:
            return JsonResponse({
                "error": "Text-to-speech service is not configured",
                "fallback": True
            }, status=503)

        # Validate API key format
        if not settings.ELEVEN_LABS_API_KEY.startswith(''):
            print("Invalid ElevenLabs API key format")
            return JsonResponse({"error": "Invalid API key format"}, status=500)

        # ElevenLabs API endpoint
        VOICE_ID = "CwhRBWXzGAHq8TQ4Fs17"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": settings.ELEVEN_LABS_API_KEY
        }
        
        # Add character limit check
        if len(text) > 2000:  # ElevenLabs free tier limit
            text = text[:2000]
            print("Text truncated to 2000 characters")
        
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }

        print(f"Making request to ElevenLabs API with text: {text[:50]}...")
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code == 401:
            return JsonResponse({
                "error": "Text-to-speech service is temporarily unavailable",
                "fallback": True,
                "details": "Authentication failed - please try again later"
            }, status=503)
        elif response.status_code == 429:  # Rate limit
            return JsonResponse({
                "error": "Text-to-speech rate limit reached",
                "fallback": True,
                "details": "Please try again later"
            }, status=429)
        elif response.status_code != 200:
            print(f"ElevenLabs API error: Status {response.status_code}")
            print(f"Response content: {response.text}")
            return JsonResponse({
                "error": f"ElevenLabs API error: {response.status_code}",
                "details": response.text
            }, status=500)

        print("Successfully received audio response")
        audio_base64 = base64.b64encode(response.content).decode('utf-8')
        return JsonResponse({"audio": audio_base64})
            
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        print(f"Request body: {request.body}")
        return JsonResponse({
            "error": "Invalid JSON in request body",
            "details": str(e)
        }, status=400)
    except Exception as e:
        import traceback
        print(f"Error in text_to_speech: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            "error": str(e),
            "stack_trace": traceback.format_exc()
        }, status=500)

def get_response(request):
    if request.method == 'POST':
        user_input = request.POST.get("user_input", "").strip()
        
        if user_input:
            try:
                model = genai.GenerativeModel(
                    model_name="gemini-1.0-pro",
                    generation_config=generation_config
                )

                context = f"""You are a helpful AI assistant. Keep your responses concise and natural, as they will be spoken by a 3D character. 
                Please respond in Hindi (using Devanagari script) to the following query: {user_input}"""
                
                response = model.generate_content(context)
                response_text = response.text if response else "मैं क्षमा चाहता हूं, लेकिन मैं जवाब नहीं दे पाया।"
                
                return JsonResponse({"response": response_text})
            except Exception as e:
                return JsonResponse({"response": f"क्षमा करें, एक त्रुटि हुई: {str(e)}"})
        
        return JsonResponse({"response": "मुझे कोई इनपुट नहीं मिला। कृपय फिर स प्रयास करें।"})
