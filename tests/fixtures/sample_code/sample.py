"""Sample Python code for testing."""
from typing import List, Optional
from app.domain.models import User


class UserService:
    """User service for managing users."""
    
    def __init__(self, repository):
        self.repository = repository
    
    def find_by_id(self, user_id: int) -> Optional[User]:
        """Find user by ID."""
        return self.repository.find_by_id(user_id)
    
    def find_all(self) -> List[User]:
        """Find all users."""
        return self.repository.find_all()
