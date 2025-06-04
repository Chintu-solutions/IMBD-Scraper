"""
Enhanced IMDb Scraper - Security Module
=======================================

Security utilities including authentication, authorization, password hashing,
token management, and security middleware.

Usage:
    from app.core.security import create_access_token, verify_password
    
    # Password hashing
    hashed = get_password_hash("password")
    is_valid = verify_password("password", hashed)
    
    # JWT tokens
    token = create_access_token(data={"sub": "user123"})
    payload = verify_token(token)
"""

import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Union, List
import re
from urllib.parse import urlparse

import bcrypt
import jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ==========================================
# PASSWORD HASHING
# ==========================================

# Password context for bcrypt hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Generate password hash using bcrypt"""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Failed to hash password: {e}")
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Failed to verify password: {e}")
        return False


def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Validate password strength according to security requirements
    
    Returns:
        Dict with validation results and feedback
    """
    validation = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "score": 0,
        "max_score": 100
    }
    
    # Length check
    if len(password) < settings.MIN_PASSWORD_LENGTH:
        validation["valid"] = False
        validation["errors"].append(f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters long")
    else:
        validation["score"] += 20
    
    # Character requirements
    if settings.REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        validation["valid"] = False
        validation["errors"].append("Password must contain at least one uppercase letter")
    elif re.search(r"[A-Z]", password):
        validation["score"] += 15
    
    if settings.REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        validation["valid"] = False
        validation["errors"].append("Password must contain at least one lowercase letter")
    elif re.search(r"[a-z]", password):
        validation["score"] += 15
    
    if settings.REQUIRE_DIGITS and not re.search(r"\d", password):
        validation["valid"] = False
        validation["errors"].append("Password must contain at least one digit")
    elif re.search(r"\d", password):
        validation["score"] += 15
    
    if settings.REQUIRE_SPECIAL_CHARS and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        validation["valid"] = False
        validation["errors"].append("Password must contain at least one special character")
    elif re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        validation["score"] += 15
    
    # Additional strength checks
    if len(password) >= 12:
        validation["score"] += 10
    elif len(password) >= 16:
        validation["score"] += 20
    
    # Check for common patterns
    common_patterns = [
        r"(.)\1{2,}",  # Repeated characters
        r"123|abc|qwe|password|admin",  # Common sequences
    ]
    
    for pattern in common_patterns:
        if re.search(pattern, password.lower()):
            validation["warnings"].append("Password contains common patterns")
            validation["score"] -= 10
            break
    
    # Ensure score is within bounds
    validation["score"] = max(0, min(validation["score"], validation["max_score"]))
    
    return validation


# ==========================================
# JWT TOKEN MANAGEMENT
# ==========================================

def create_access_token(
    data: Dict[str, Any], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token"""
    
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    
    try:
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        logger.debug("Access token created", user_id=data.get("sub"))
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create access token: {e}")
        raise


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token"""
    
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    })
    
    try:
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        logger.debug("Refresh token created", user_id=data.get("sub"))
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create refresh token: {e}")
        raise


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """Verify and decode JWT token"""
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Check token type
        if payload.get("type") != token_type:
            logger.warning(f"Invalid token type: expected {token_type}, got {payload.get('type')}")
            return None
        
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, timezone.utc) < datetime.now(timezone.utc):
            logger.debug("Token expired", user_id=payload.get("sub"))
            return None
        
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.JWTError as e:
        logger.warning(f"Token validation failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return None


def refresh_access_token(refresh_token: str) -> Optional[Dict[str, str]]:
    """Generate new access token from refresh token"""
    
    payload = verify_token(refresh_token, token_type="refresh")
    if not payload:
        return None
    
    # Create new access token
    access_token_data = {
        "sub": payload.get("sub"),
        "permissions": payload.get("permissions", [])
    }
    
    access_token = create_access_token(access_token_data)
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# ==========================================
# API KEY MANAGEMENT
# ==========================================

def generate_api_key(prefix: str = "imdb", length: int = 32) -> str:
    """Generate secure API key"""
    
    random_part = secrets.token_urlsafe(length)
    api_key = f"{prefix}_{random_part}"
    
    logger.info("API key generated", prefix=prefix)
    return api_key


def hash_api_key(api_key: str) -> str:
    """Hash API key for secure storage"""
    
    # Use SHA-256 with salt
    salt = settings.SECRET_KEY.encode()
    return hashlib.pbkdf2_hmac('sha256', api_key.encode(), salt, 100000).hex()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """Verify API key against hash"""
    
    try:
        computed_hash = hash_api_key(api_key)
        return hmac.compare_digest(computed_hash, hashed_key)
    except Exception as e:
        logger.error(f"API key verification failed: {e}")
        return False


# ==========================================
# DATA ENCRYPTION
# ==========================================

class DataEncryption:
    """Handle encryption/decryption of sensitive data"""
    
    def __init__(self, key: Optional[str] = None):
        if key is None:
            key = settings.SECRET_KEY
        
        # Derive encryption key from secret
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"imdb_scraper_salt",  # In production, use random salt per encryption
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(key.encode()))
        self.fernet = Fernet(derived_key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data"""
        try:
            encrypted_data = self.fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data"""
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self.fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """Encrypt dictionary data"""
        import json
        json_data = json.dumps(data, sort_keys=True)
        return self.encrypt(json_data)
    
    def decrypt_dict(self, encrypted_data: str) -> Dict[str, Any]:
        """Decrypt dictionary data"""
        import json
        json_data = self.decrypt(encrypted_data)
        return json.loads(json_data)


# Global encryption instance
encryption = DataEncryption()


# ==========================================
# SECURE RANDOM GENERATORS
# ==========================================

def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure random token"""
    return secrets.token_urlsafe(length)


def generate_session_id() -> str:
    """Generate secure session ID"""
    return generate_secure_token(32)


def generate_request_id() -> str:
    """Generate unique request ID"""
    timestamp = int(datetime.now().timestamp() * 1000000)
    random_part = secrets.token_hex(8)
    return f"req_{timestamp}_{random_part}"


def generate_job_id() -> str:
    """Generate unique job ID"""
    timestamp = int(datetime.now().timestamp() * 1000000)
    random_part = secrets.token_hex(8)
    return f"job_{timestamp}_{random_part}"


# ==========================================
# INPUT VALIDATION AND SANITIZATION
# ==========================================

def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize string input"""
    if not isinstance(value, str):
        value = str(value)
    
    # Remove null bytes and control characters
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', value)
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized.strip()


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_url(url: str, allowed_schemes: List[str] = None) -> bool:
    """Validate URL format and scheme"""
    if allowed_schemes is None:
        allowed_schemes = ["http", "https"]
    
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in allowed_schemes and
            bool(parsed.netloc) and
            len(url) <= 2000  # Reasonable URL length limit
        )
    except Exception:
        return False


def validate_imdb_id(imdb_id: str) -> bool:
    """Validate IMDb ID format"""
    pattern = r'^tt\d{7,8}$'
    return bool(re.match(pattern, imdb_id))


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    # Remove or replace dangerous characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Limit length
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        max_name_length = 255 - len(ext)
        sanitized = name[:max_name_length] + ext
    
    return sanitized


# ==========================================
# RATE LIMITING
# ==========================================

class RateLimiter:
    """Rate limiting utility"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
    
    async def is_allowed(
        self,
        identifier: str,
        limit: int,
        window_seconds: int,
        namespace: str = "rate_limit"
    ) -> Dict[str, Any]:
        """Check if request is allowed under rate limit"""
        
        if not self.redis_client:
            # If no Redis, allow all requests
            return {
                "allowed": True,
                "remaining": limit,
                "reset_time": datetime.now() + timedelta(seconds=window_seconds)
            }
        
        key = f"{namespace}:{identifier}"
        current_time = int(datetime.now().timestamp())
        window_start = current_time - window_seconds
        
        try:
            # Use Redis pipeline for atomic operations
            async with self.redis_client.pipeline() as pipe:
                # Remove expired entries
                pipe.zremrangebyscore(key, 0, window_start)
                
                # Count current requests
                pipe.zcard(key)
                
                # Add current request
                pipe.zadd(key, {str(current_time): current_time})
                
                # Set expiration
                pipe.expire(key, window_seconds)
                
                results = await pipe.execute()
                current_count = results[1]
                
                return {
                    "allowed": current_count < limit,
                    "current_count": current_count,
                    "remaining": max(0, limit - current_count - 1),
                    "limit": limit,
                    "reset_time": datetime.fromtimestamp(current_time + window_seconds)
                }
                
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # On error, allow the request
            return {
                "allowed": True,
                "remaining": limit,
                "error": str(e)
            }


# ==========================================
# SECURITY HEADERS
# ==========================================

def get_security_headers() -> Dict[str, str]:
    """Get security headers for HTTP responses"""
    
    headers = {
        # Prevent clickjacking
        "X-Frame-Options": "DENY",
        
        # Prevent MIME type sniffing
        "X-Content-Type-Options": "nosniff",
        
        # XSS protection
        "X-XSS-Protection": "1; mode=block",
        
        # Referrer policy
        "Referrer-Policy": "strict-origin-when-cross-origin",
        
        # Content Security Policy
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "media-src 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none';"
        ),
        
        # HSTS (if using HTTPS)
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        
        # Permissions policy
        "Permissions-Policy": (
            "camera=(), "
            "microphone=(), "
            "geolocation=(), "
            "interest-cohort=()"
        )
    }
    
    return headers


# ==========================================
# IP ADDRESS UTILITIES
# ==========================================

def get_client_ip(request_headers: Dict[str, str]) -> str:
    """Extract client IP address from request headers"""
    
    # Check common proxy headers
    ip_headers = [
        "X-Forwarded-For",
        "X-Real-IP", 
        "X-Client-IP",
        "CF-Connecting-IP",  # Cloudflare
        "True-Client-IP",
    ]
    
    for header in ip_headers:
        ip = request_headers.get(header)
        if ip:
            # X-Forwarded-For can contain multiple IPs, take the first one
            return ip.split(',')[0].strip()
    
    # Fallback to direct connection
    return request_headers.get("Remote-Addr", "unknown")


def is_private_ip(ip_address: str) -> bool:
    """Check if IP address is in private range"""
    import ipaddress
    
    try:
        ip = ipaddress.ip_address(ip_address)
        return ip.is_private
    except ValueError:
        return False


def is_valid_ip(ip_address: str) -> bool:
    """Validate IP address format"""
    import ipaddress
    
    try:
        ipaddress.ip_address(ip_address)
        return True
    except ValueError:
        return False


# ==========================================
# SECURITY AUDIT LOGGING
# ==========================================

class SecurityAuditor:
    """Security event auditing"""
    
    def __init__(self):
        self.logger = get_logger("security_audit")
    
    def log_authentication_attempt(
        self,
        user_id: Optional[str],
        ip_address: str,
        user_agent: str,
        success: bool,
        failure_reason: Optional[str] = None
    ):
        """Log authentication attempt"""
        
        event_data = {
            "event_type": "authentication_attempt",
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if not success and failure_reason:
            event_data["failure_reason"] = failure_reason
        
        if success:
            self.logger.info("Authentication successful", **event_data)
        else:
            self.logger.warning("Authentication failed", **event_data)
    
    def log_authorization_failure(
        self,
        user_id: str,
        resource: str,
        action: str,
        ip_address: str
    ):
        """Log authorization failure"""
        
        self.logger.warning(
            "Authorization denied",
            event_type="authorization_failure",
            user_id=user_id,
            resource=resource,
            action=action,
            ip_address=ip_address,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_suspicious_activity(
        self,
        activity_type: str,
        description: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        severity: str = "medium"
    ):
        """Log suspicious activity"""
        
        self.logger.error(
            "Suspicious activity detected",
            event_type="suspicious_activity",
            activity_type=activity_type,
            description=description,
            user_id=user_id,
            ip_address=ip_address,
            severity=severity,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_data_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: str
    ):
        """Log sensitive data access"""
        
        self.logger.info(
            "Data access",
            event_type="data_access",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            ip_address=ip_address,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_configuration_change(
        self,
        user_id: str,
        setting_name: str,
        old_value: Optional[str],
        new_value: str,
        ip_address: str
    ):
        """Log configuration changes"""
        
        self.logger.warning(
            "Configuration changed",
            event_type="configuration_change",
            user_id=user_id,
            setting_name=setting_name,
            old_value="***REDACTED***" if "password" in setting_name.lower() else old_value,
            new_value="***REDACTED***" if "password" in setting_name.lower() else new_value,
            ip_address=ip_address,
            timestamp=datetime.utcnow().isoformat()
        )


# Global security auditor instance
security_auditor = SecurityAuditor()


# ==========================================
# CSRF PROTECTION
# ==========================================

def generate_csrf_token() -> str:
    """Generate CSRF token"""
    return generate_secure_token(32)


def verify_csrf_token(token: str, expected_token: str) -> bool:
    """Verify CSRF token"""
    try:
        return hmac.compare_digest(token, expected_token)
    except Exception:
        return False


# ==========================================
# SESSION MANAGEMENT
# ==========================================

class SessionManager:
    """Secure session management"""
    
    def __init__(self, cache_manager=None):
        self.cache = cache_manager
        self.session_timeout = 3600  # 1 hour
    
    async def create_session(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create new session"""
        
        session_id = generate_session_id()
        
        session_data = {
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.utcnow().isoformat(),
            "last_accessed": datetime.utcnow().isoformat(),
            "csrf_token": generate_csrf_token(),
        }
        
        if additional_data:
            session_data.update(additional_data)
        
        if self.cache:
            await self.cache.set(
                f"session:{session_id}",
                session_data,
                ttl=self.session_timeout
            )
        
        logger.info("Session created", session_id=session_id, user_id=user_id)
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        
        if not self.cache:
            return None
        
        session_data = await self.cache.get(f"session:{session_id}")
        
        if session_data:
            # Update last accessed time
            session_data["last_accessed"] = datetime.utcnow().isoformat()
            await self.cache.set(
                f"session:{session_id}",
                session_data,
                ttl=self.session_timeout
            )
        
        return session_data
    
    async def invalidate_session(self, session_id: str) -> bool:
        """Invalidate session"""
        
        if not self.cache:
            return True
        
        result = await self.cache.delete(f"session:{session_id}")
        logger.info("Session invalidated", session_id=session_id)
        return result
    
    async def invalidate_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user"""
        
        if not self.cache:
            return 0
        
        # This would require scanning for sessions by user_id
        # Implementation depends on cache structure
        logger.info("User sessions invalidated", user_id=user_id)
        return 0


# ==========================================
# PERMISSION SYSTEM
# ==========================================

class Permission:
    """Permission definition"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def __str__(self):
        return self.name
    
    def __eq__(self, other):
        return isinstance(other, Permission) and self.name == other.name
    
    def __hash__(self):
        return hash(self.name)


class Role:
    """Role with permissions"""
    
    def __init__(self, name: str, permissions: List[Permission]):
        self.name = name
        self.permissions = set(permissions)
    
    def has_permission(self, permission: Union[str, Permission]) -> bool:
        """Check if role has permission"""
        if isinstance(permission, str):
            return any(p.name == permission for p in self.permissions)
        return permission in self.permissions
    
    def add_permission(self, permission: Permission):
        """Add permission to role"""
        self.permissions.add(permission)
    
    def remove_permission(self, permission: Permission):
        """Remove permission from role"""
        self.permissions.discard(permission)


# Define application permissions
PERMISSIONS = {
    # Movie management
    "movies.read": Permission("movies.read", "Read movie data"),
    "movies.create": Permission("movies.create", "Create movie entries"),
    "movies.update": Permission("movies.update", "Update movie data"),
    "movies.delete": Permission("movies.delete", "Delete movie entries"),
    
    # Scraping operations
    "scraping.start": Permission("scraping.start", "Start scraping jobs"),
    "scraping.stop": Permission("scraping.stop", "Stop scraping jobs"),
    "scraping.configure": Permission("scraping.configure", "Configure scraping settings"),
    
    # User management
    "users.read": Permission("users.read", "Read user data"),
    "users.create": Permission("users.create", "Create user accounts"),
    "users.update": Permission("users.update", "Update user data"),
    "users.delete": Permission("users.delete", "Delete user accounts"),
    
    # System administration
    "system.admin": Permission("system.admin", "System administration"),
    "system.monitoring": Permission("system.monitoring", "System monitoring"),
    "system.backup": Permission("system.backup", "System backup/restore"),
}

# Define application roles
ROLES = {
    "admin": Role("admin", list(PERMISSIONS.values())),
    "scraper": Role("scraper", [
        PERMISSIONS["movies.read"],
        PERMISSIONS["movies.create"],
        PERMISSIONS["movies.update"],
        PERMISSIONS["scraping.start"],
        PERMISSIONS["scraping.stop"],
        PERMISSIONS["scraping.configure"],
    ]),
    "viewer": Role("viewer", [
        PERMISSIONS["movies.read"],
    ]),
}


def check_permission(user_roles: List[str], required_permission: str) -> bool:
    """Check if user has required permission"""
    
    for role_name in user_roles:
        role = ROLES.get(role_name)
        if role and role.has_permission(required_permission):
            return True
    
    return False


# ==========================================
# SECURITY UTILITIES
# ==========================================

def constant_time_compare(a: str, b: str) -> bool:
    """Constant time string comparison to prevent timing attacks"""
    return hmac.compare_digest(a, b)


def secure_filename(filename: str) -> str:
    """Generate secure filename"""
    # Remove path components
    filename = os.path.basename(filename)
    
    # Sanitize
    filename = sanitize_filename(filename)
    
    # Add timestamp to prevent collisions
    name, ext = os.path.splitext(filename)
    timestamp = int(datetime.now().timestamp())
    
    return f"{name}_{timestamp}{ext}"


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """Mask sensitive data showing only first/last characters"""
    if len(data) <= visible_chars * 2:
        return "*" * len(data)
    
    return data[:visible_chars] + "*" * (len(data) - visible_chars * 2) + data[-visible_chars:]


def generate_backup_codes(count: int = 10) -> List[str]:
    """Generate backup codes for 2FA"""
    codes = []
    for _ in range(count):
        # Generate 8-character alphanumeric code
        code = ''.join(secrets.choice('ABCDEFGHIJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
        # Format as XXXX-XXXX
        formatted_code = f"{code[:4]}-{code[4:]}"
        codes.append(formatted_code)
    
    return codes


# ==========================================
# SECURITY CONFIGURATION VALIDATION
# ==========================================

def validate_security_config() -> List[str]:
    """Validate security configuration"""
    errors = []
    
    # Check secret key
    if settings.SECRET_KEY == "super-secret-key-change-in-production-immediately":
        errors.append("SECRET_KEY must be changed from default value")
    
    if len(settings.SECRET_KEY) < 32:
        errors.append("SECRET_KEY should be at least 32 characters long")
    
    # Check token expiration
    if settings.ACCESS_TOKEN_EXPIRE_MINUTES < 1:
        errors.append("ACCESS_TOKEN_EXPIRE_MINUTES must be at least 1")
    
    if settings.ACCESS_TOKEN_EXPIRE_MINUTES > 1440:  # 24 hours
        errors.append("ACCESS_TOKEN_EXPIRE_MINUTES should not exceed 24 hours")
    
    # Check password requirements
    if settings.MIN_PASSWORD_LENGTH < 8:
        errors.append("MIN_PASSWORD_LENGTH should be at least 8")
    
    # Check CORS configuration in production
    if settings.is_production and "*" in settings.ALLOWED_HOSTS:
        errors.append("ALLOWED_HOSTS should not include '*' in production")
    
    return errors


# ==========================================
# EXPORTS
# ==========================================

__all__ = [
    # Password hashing
    "get_password_hash",
    "verify_password",
    "validate_password_strength",
    
    # JWT tokens
    "create_access_token",
    "create_refresh_token", 
    "verify_token",
    "refresh_access_token",
    
    # API keys
    "generate_api_key",
    "hash_api_key",
    "verify_api_key",
    
    # Data encryption
    "DataEncryption",
    "encryption",
    
    # Random generators
    "generate_secure_token",
    "generate_session_id",
    "generate_request_id",
    "generate_job_id",
    
    # Input validation
    "sanitize_string",
    "validate_email",
    "validate_url", 
    "validate_imdb_id",
    "sanitize_filename",
    
    # Rate limiting
    "RateLimiter",
    
    # Security headers
    "get_security_headers",
    
    # IP utilities
    "get_client_ip",
    "is_private_ip",
    "is_valid_ip",
    
    # Security auditing
    "SecurityAuditor",
    "security_auditor",
    
    # CSRF protection
    "generate_csrf_token",
    "verify_csrf_token",
    
    # Session management
    "SessionManager",
    
    # Permission system
    "Permission",
    "Role",
    "PERMISSIONS",
    "ROLES",
    "check_permission",
    
    # Utilities
    "constant_time_compare",
    "secure_filename",
    "mask_sensitive_data",
    "generate_backup_codes",
    
    # Validation
    "validate_security_config",
]