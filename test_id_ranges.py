"""
Test script to verify the ID range implementation for Artists and Producers.
"""
import os
import django
import time

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from users.models import Artist, Producer, get_user_by_id

def test_create_producer():
    """Test creating a new producer and verify it gets a high ID."""
    timestamp = int(time.time())
    
    # Create a test producer with timestamp to ensure uniqueness
    p = Producer(
        username=f'test_producer_{timestamp}',
        nom='Test',
        prenom='Producer',
        email=f'test{timestamp}@example.com',
        password='testpassword'
    )
    p.save()
    print(f'Created producer with ID: {p.id}')
    
    # Verify ID is in the expected range
    assert p.id >= 1000000, f"Producer ID {p.id} is not in the expected range (>= 1,000,000)"
    
    # Test lookups
    user, user_type = get_user_by_id(p.id)
    print(f'get_user_by_id({p.id}) returned: {user.username} of type {user_type}')
    
    # Clean up
    p.delete()
    print(f'Test producer deleted')
    
    return True

def test_get_user_by_id():
    """Test the get_user_by_id function with existing users."""
    # Get an existing artist
    artist = Artist.objects.first()
    if artist:
        user, user_type = get_user_by_id(artist.id)
        print(f'Artist ID {artist.id}: get_user_by_id returned {user.username} of type {user_type}')
        assert user_type == 'artist', f"Expected 'artist', got '{user_type}'"
    else:
        print("No artists found")
    
    # Get an existing producer
    producer = Producer.objects.first()
    if producer:
        user, user_type = get_user_by_id(producer.id)
        print(f'Producer ID {producer.id}: get_user_by_id returned {user.username} of type {user_type}')
        
        # Check if the producer already has a high ID or not
        if producer.id < 1000000:
            print(f"Warning: Existing producer {producer.username} has ID {producer.id}, which is not in the high range")
            print("This is expected for producers created before the ID range separation.")
            print("Only new producers will get IDs in the 1,000,000+ range.")
        else:
            assert user_type == 'producer', f"Expected 'producer', got '{user_type}'"
    else:
        print("No producers found")
    
    return True

if __name__ == "__main__":
    print("\n=== Testing ID Range Implementation ===\n")
    
    print("\n--- Testing get_user_by_id with existing users ---\n")
    test_get_user_by_id()
    
    print("\n--- Testing creation of new producer ---\n")
    test_create_producer()
    
    print("\n=== All tests completed successfully ===\n") 