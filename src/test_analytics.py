from services.analytics_service import calculate_profile_completeness

def test_profile_completeness():
    print("🧪 Testing Profile Completeness Calculation...")
    
    # 1. Empty profile
    data_empty = {}
    score_empty = calculate_profile_completeness(data_empty)
    print(f"Empty Profile Score: {score_empty} (Expected: 0)")
    assert score_empty == 0
    
    # 2. Partial profile
    data_partial = {
        'phone': '+79991234567',  # +15
        'website': 'example.com',  # +15
        'photos_count': 1          # +5
    }
    score_partial = calculate_profile_completeness(data_partial)
    print(f"Partial Profile Score: {score_partial} (Expected: 35)")
    assert score_partial == 35
    
    # 3. Full profile
    data_full = {
        'phone': '+79991234567',       # +15
        'website': 'example.com',       # +15
        'schedule': 'Mon-Fri 09-18',    # +10
        'photos_count': 10,             # +15
        'services_count': 10,           # +15
        'description': 'A very long description of the business.', # +10
        'messengers': ['telegram'],     # +10
        'is_verified': True             # +10
    }
    score_full = calculate_profile_completeness(data_full)
    print(f"Full Profile Score: {score_full} (Expected: 100)")
    assert score_full == 100
    
    # 4. Mixed types (robustness check)
    data_mixed = {
        'phone': 79991234567,           # should handle int
        'photos_count': '10',           # should handle str
        'services_count': None          # should handle None
    }
    score_mixed = calculate_profile_completeness(data_mixed)
    print(f"Mixed Types Score: {score_mixed} (Expected around 30)") 
    # Phone (if conv to str len > 5) -> +15. Photos '10' -> +15. Total 30.
    assert score_mixed == 30

    print("\n✅ All Analytics Tests Passed!")

if __name__ == "__main__":
    test_profile_completeness()
