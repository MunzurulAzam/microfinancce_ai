import http.client
import json

def verify_preload():
    print(f"🔍 Checking http://localhost:5000/api/stats for pre-loaded data...")
    
    try:
        conn = http.client.HTTPConnection("localhost", 5000)
        conn.request("GET", "/api/stats")
        response = conn.getresponse()
        
        if response.status == 200:
            data = json.loads(response.read().decode())
            if data.get('success') and data.get('stats'):
                stats = data['stats']
                print("✅ Backend has pre-loaded data!")
                print(f"📊 Total Clients: {stats.get('total_clients')}")
                print(f"📊 Total Portfolio: {stats.get('total_loan_portfolio')} UGX")
                return True
            else:
                print("❌ Backend returned 200 but no stats found.")
                print(f"Response: {data}")
        elif response.status == 400:
            print("❌ Backend is running but no data is loaded (Returned 400).")
        else:
            print(f"❌ Backend returned status code {response.status}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("💡 Is the Flask server running? Try starting it with 'python app.py'")
    
    return False

if __name__ == "__main__":
    verify_preload()
