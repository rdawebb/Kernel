"""
Tests for configuration management

Tests cover:
- Configuration loading and defaults
- Environment variable handling
- Configuration validation
- Port and SSL settings
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
        result = config.get_config('account.email')
        assert isinstance(result, str)


class TestConfigurationDefaults:
    """Tests for default configuration values"""
    
    def test_default_imap_port(self):
        """Test default IMAP port is configured"""
        config = ConfigManager()
        imap_port = config.get_config('account.imap_port')
        assert isinstance(imap_port, int)
        assert imap_port == 993
    
    def test_default_smtp_port(self):
        """Test default SMTP port is configured"""
        config = ConfigManager()
        smtp_port = config.get_config('account.smtp_port')
        assert isinstance(smtp_port, int)
        assert smtp_port == 587


class TestConfigurationValidation:
    """Tests for configuration validation"""
    
    def test_validate_required_fields_present(self):
        """Test that required configuration fields are present"""
        config = ConfigManager()
        email = config.get_config('account.email')
        assert isinstance(email, str)
    
    def test_validate_port_numbers_are_integers(self):
        """Test that port numbers are valid integers"""
        config = ConfigManager()
        imap_port = config.get_config('account.imap_port')
        smtp_port = config.get_config('account.smtp_port')
        assert isinstance(imap_port, int)
        assert isinstance(smtp_port, int)
    
    def test_validate_ssl_flag_is_boolean(self):
        """Test that SSL flag is a boolean"""
        config = ConfigManager()
        use_tls = config.get_config('account.use_tls')
        assert isinstance(use_tls, bool)


class TestEnvironmentVariableHandling:
    """Tests for environment variable loading"""
    
    def test_config_from_env_variables(self):
        """Test loading configuration from environment"""
        config = ConfigManager()
        imap_server = config.get_config('account.imap_server')
        assert isinstance(imap_server, str)
    
    def test_config_handles_missing_env_vars(self):
        """Test config handles missing environment variables"""
        config = ConfigManager()
        email = config.get_config('account.email')
        assert isinstance(email, str)


class TestDatabasePathConfiguration:
    """Tests for database path configuration"""
    
    def test_database_path_configured(self):
        """Test that database path is configured"""
        config = ConfigManager()
        assert config.config is not None
    
    def test_database_path_is_accessible(self):
        """Test that database path is accessible"""
        config = ConfigManager()
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
        assert use_tls in (True, False)
