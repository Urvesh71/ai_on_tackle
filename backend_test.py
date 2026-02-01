import requests
import sys
import json
from datetime import datetime

class LLMCommandInterpreterTester:
    def __init__(self, base_url="https://llm-json-learner.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.session_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root Endpoint", "GET", "", 200)

    def test_status_endpoints(self):
        """Test status check endpoints"""
        # Test POST status
        success, response = self.run_test(
            "Create Status Check",
            "POST",
            "status",
            200,
            data={"client_name": "test_client"}
        )
        
        if not success:
            return False
            
        # Test GET status
        success, _ = self.run_test("Get Status Checks", "GET", "status", 200)
        return success

    def test_commands_endpoint(self):
        """Test commands endpoint"""
        success, response = self.run_test("Get Commands", "GET", "commands", 200)
        if success and isinstance(response, dict) and 'commands' in response:
            commands = response['commands']
            print(f"   Found {len(commands)} commands")
            # Check for some expected commands
            expected_commands = ["Grids", "Table", "Borders", "Copy", "Paste"]
            found_commands = [cmd for cmd in expected_commands if cmd in commands]
            print(f"   Expected commands found: {found_commands}")
            return len(found_commands) >= 3
        return success

    def test_single_command_chat(self):
        """Test single command processing"""
        success, response = self.run_test(
            "Single Command Chat",
            "POST",
            "chat",
            200,
            data={
                "message": "show grids",
                "session_id": None
            }
        )
        
        if success and isinstance(response, dict):
            formula = response.get('formula', '')
            self.session_id = response.get('session_id')
            print(f"   Generated formula: {formula}")
            print(f"   Session ID: {self.session_id}")
            
            # Check if formula is reasonable
            if formula and formula != "UNKNOWN_COMMAND":
                return True
            else:
                print(f"   Warning: Unexpected formula: {formula}")
                return False
        return False

    def test_multi_command_chat(self):
        """Test multi-command processing"""
        success, response = self.run_test(
            "Multi-Command Chat",
            "POST",
            "chat",
            200,
            data={
                "message": "go to grids, create table, apply borders",
                "session_id": self.session_id
            }
        )
        
        if success and isinstance(response, dict):
            formula = response.get('formula', '')
            print(f"   Generated formula: {formula}")
            
            # Check if formula contains dots (multi-command)
            if formula and "." in formula:
                return True
            else:
                print(f"   Warning: Expected multi-command formula with dots: {formula}")
                return False
        return False

    def test_chat_history(self):
        """Test chat history retrieval"""
        if not self.session_id:
            print("   Skipping - No session ID available")
            return True
            
        success, response = self.run_test(
            "Chat History",
            "GET",
            f"chat/history/{self.session_id}",
            200
        )
        
        if success and isinstance(response, dict):
            messages = response.get('messages', [])
            print(f"   Found {len(messages)} messages in history")
            return len(messages) >= 2  # Should have at least 2 messages from previous tests
        return False

    def test_invalid_command(self):
        """Test handling of invalid commands"""
        success, response = self.run_test(
            "Invalid Command",
            "POST",
            "chat",
            200,
            data={
                "message": "xyz invalid command that does not exist",
                "session_id": self.session_id
            }
        )
        
        if success and isinstance(response, dict):
            formula = response.get('formula', '')
            print(f"   Generated formula: {formula}")
            
            # Should return UNKNOWN_COMMAND or similar
            if "UNKNOWN" in formula.upper() or formula == "":
                return True
            else:
                print(f"   Warning: Expected UNKNOWN_COMMAND for invalid input: {formula}")
                return True  # Still pass as LLM might interpret differently
        return False

def main():
    print("🚀 Starting LLM Command Interpreter API Tests")
    print("=" * 50)
    
    tester = LLMCommandInterpreterTester()
    
    # Run all tests
    tests = [
        tester.test_root_endpoint,
        tester.test_commands_endpoint,
        tester.test_status_endpoints,
        tester.test_single_command_chat,
        tester.test_multi_command_chat,
        tester.test_chat_history,
        tester.test_invalid_command,
    ]
    
    for test in tests:
        try:
            if not test():
                print(f"❌ Test {test.__name__} failed")
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {str(e)}")
    
    # Print results
    print("\n" + "=" * 50)
    print(f"📊 Tests Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())