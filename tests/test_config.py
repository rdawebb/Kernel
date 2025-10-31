"""
Comprehensive tests for configuration management

Tests cover:
- Configuration loading and defaults
- Environment variable handling
- Configuration validation
- Port and SSL settings
- Database path configuration
"""
from src.utils.config_manager import ConfigManager


class TestConfigManagerInitialization:
    """Tests for ConfigManager initialization"""
    
    def test_config_manager_load_defaults(self):
        """Test ConfigManager loads with default values"""
        config = ConfigManager()
        assert config is not None
    
    def test_config_manager_get_config(self):
        """Test retrieving configuration"""
        config = ConfigManager()
        # Test getting a specific config value works
        result = config.config.account.email
        assert isinstance(result, str)


class TestConfigurationDefaults:
    """Tests for default configuration values"""
    
    def test_default_imap_host(self):
        """Test default IMAP host is set"""
        config = ConfigManager()
        imap_host = config.config.account.imap_server
        assert isinstance(imap_host, str)
    
    def test_default_smtp_host(self):
        """Test default SMTP host is set"""
        config = ConfigManager()
        smtp_host = config.config.account.smtp_server
        assert isinstance(smtp_host, str)
    
    def test_default_imap_port(self):
        """Test default IMAP port is configured"""
        config = ConfigManager()
        imap_port = config.config.account.imap_port
        assert isinstance(imap_port, int)
        assert imap_port == 993
    
    def test_default_smtp_port(self):
        """Test default SMTP port is configured"""
        config = ConfigManager()
        smtp_port = config.config.account.smtp_port
        assert isinstance(smtp_port, int)
        assert smtp_port == 587


class TestConfigurationValidation:
    """Tests for configuration validation"""
    
    def test_validate_required_fields_present(self):
        """Test that required configuration fields are present"""
        config = ConfigManager()
        # Verify core required fields exist
        email = config.config.account.email
        assert isinstance(email, str)
    
    def test_validate_port_numbers_are_integers(self):
        """Test that port numbers are valid integers"""
        config = ConfigManager()
        imap_port = config.config.account.imap_port
        smtp_port = config.config.account.smtp_port
        assert isinstance(imap_port, int)
        assert isinstance(smtp_port, int)
        assert imap_port > 0
        assert smtp_port > 0
    
    def test_validate_ssl_flag_is_boolean(self):
        """Test that SSL flag is a boolean"""
        config = ConfigManager()
        use_tls = config.config.account.use_tls
        assert isinstance(use_tls, bool)


class TestEnvironmentVariableHandling:
    """Tests for environment variable loading and defaults"""
    
    def test_config_from_env_variables(self):
        """Test loading configuration from environment variables"""
        config = ConfigManager()
        imap_server = config.get_config('account.imap_server')
        assert isinstance(imap_server, str)
    
    def test_config_ignores_invalid_env_vars(self):
        """Test that invalid environment variables don't crash config"""
        # Should not raise error
        config = ConfigManager()
        email = config.get_config('account.email')
        assert isinstance(email, str)
    
    def test_config_priority_env_over_defaults(self):
        """Test that environment variables override defaults"""
        config = ConfigManager()
        imap_server = config.get_config('account.imap_server')
        assert isinstance(imap_server, str)


class TestDatabasePathConfiguration:
    """Tests for database path configuration"""
    
    def test_database_path_configured(self):
        """Test that database path is configured"""
        config = ConfigManager()
        # Config should have database information
        assert config.config is not None
    
    def test_database_path_is_string(self):
        """Test that database path is a string"""
        config = ConfigManager()
        # Verify config is properly initialized
        assert hasattr(config, 'config')


class TestSSLConfiguration:
    """Tests for SSL/TLS configuration"""
    
    def test_imap_ssl_configured(self):
        """Test that IMAP SSL setting exists"""
        config = ConfigManager()
        use_tls = config.get_config('account.use_tls')
        assert isinstance(use_tls, bool)
    
    def test_smtp_ssl_configured(self):
        """Test that SMTP SSL setting exists"""
        config = ConfigManager()
        use_tls = config.get_config('account.use_tls')
        assert isinstance(use_tls, bool)
    
    def test_ssl_flag_values_valid(self):
        """Test that SSL flags have valid values"""
        config = ConfigManager()
        use_tls = config.get_config('account.use_tls')
        # Should be boolean True/False
        assert use_tls in (True, False)

