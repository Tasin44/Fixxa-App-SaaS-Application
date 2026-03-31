"""
Fixxa AI - Test Script
======================
Quick test of the AI module before Django integration.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_imports():
    """Test module imports"""
    print_section("1. Testing Imports")
    
    try:
        from fixxa_ai import (
            process_audio_from_file,
            natural_language_query,
            check_database_health,
            validate_user_id
        )
        print("✅ All functions imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("   Run: pip install -r requirements.txt")
        return False


def test_configuration():
    """Test environment configuration"""
    print_section("2. Testing Configuration")
    
    try:
        from fixxa_ai.config import Config
        
        Config.validate()
        print("✅ Configuration valid")
        print(f"   ✓ OPENAI_API_KEY: {Config.OPENAI_API_KEY[:20]}...")
        print(f"   ✓ DATABASE_URL: {Config.DATABASE_URL[:30]}...")
        return True
    
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        print("   Create .env file with:")
        print("   - OPENAI_API_KEY=your-key")
        print("   - DATABASE_URL=postgresql://...")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_database():
    """Test database connection"""
    print_section("3. Testing Database Connection")
    
    try:
        from fixxa_ai import check_database_health
        
        health = check_database_health()
        
        if health['status'] == 'healthy':
            print(f"✅ Database status: {health['status']}")
            print(f"   Database: {health['database']}")
            print(f"   Tables found: {health.get('table_count', 0)}")
            
            if health.get('tables'):
                print("\n   Sample tables:")
                for table in health['tables'][:5]:
                    print(f"      - {table}")
            
            return True
        else:
            print(f"❌ Database status: {health['status']}")
            print(f"   Error: {health.get('message')}")
            return False
    
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_chatbot():
    """Test SQL chatbot"""
    print_section("4. Testing SQL Chatbot (Optional)")
    
    print("⏭️  Skipping chatbot test (requires valid user_id)")
    print("   Test this from Django backend with real user_id")
    print("   Example: natural_language_query(request.user.id, 'How many clients?')")
    return True


def main():
    print_section("Fixxa AI - Module Test")
    print("Testing the AI module before Django integration.\n")
    
    tests = []
    
    # Test imports
    if not test_imports():
        print("\n⚠️  Install dependencies first: pip install -r requirements.txt")
        return
    tests.append(("Imports", True))
    
    # Test configuration
    if not test_configuration():
        print("\n⚠️  Configure .env file before proceeding")
        return
    tests.append(("Configuration", True))
    
    # Test database
    db_ok = test_database()
    tests.append(("Database", db_ok))
    
    if not db_ok:
        print("\n⚠️  Database connection failed - check DATABASE_URL")
        print("   The URL should point to your Django PostgreSQL database")
    
    # Chatbot test (skipped, needs user_id)
    tests.append(("Chatbot", test_chatbot()))
    
    # Summary
    print_section("Test Summary")
    
    for test_name, passed in tests:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {test_name:20} {status}")
    
    all_passed = all(passed for _, passed in tests)
    
    if all_passed:
        print("\n" + "=" * 60)
        print("   ✅ All tests passed!")
        print("=" * 60)
        print("\n   Next steps:")
        print("   1. Read BACKEND_INTEGRATION_GUIDE.md")
        print("   2. Create Django API endpoints")
        print("   3. Test with Postman (see POSTMAN_TESTING_GUIDE.md)")
        print("\n")
    else:
        print("\n⚠️  Some tests failed. Fix the issues above and try again.")


if __name__ == "__main__":
    main()
