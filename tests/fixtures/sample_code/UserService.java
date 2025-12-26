package app.domain;

import app.domain.model.User;
import java.util.List;

/**
 * Sample Java class for testing.
 */
public class UserService {
    
    private UserRepository repository;
    
    public UserService(UserRepository repository) {
        this.repository = repository;
    }
    
    public User findById(Long id) {
        return repository.findById(id);
    }
    
    public List<User> findAll() {
        return repository.findAll();
    }
}
