"""
Notification Service - Handle various notification types
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

class NotificationType(Enum):
    """Notification types"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class NotificationChannel(Enum):
    """Notification channels"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"
    LOG = "log"

class NotificationService:
    """Service for handling notifications and alerts"""
    
    def __init__(self):
        self.enabled_channels = self._get_enabled_channels()
        self.notification_queue = []
    
    def _get_enabled_channels(self) -> List[NotificationChannel]:
        """Get enabled notification channels from configuration"""
        # In real implementation, this would read from settings
        return [NotificationChannel.LOG]  # Default to logging only
    
    async def send_notification(
        self,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        channels: Optional[List[NotificationChannel]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send notification through specified channels"""
        
        if channels is None:
            channels = self.enabled_channels
        
        notification_data = {
            "id": f"notif_{int(datetime.now().timestamp() * 1000)}",
            "message": message,
            "type": notification_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "channels": [channel.value for channel in channels]
        }
        
        results = {}
        
        for channel in channels:
            try:
                if channel == NotificationChannel.LOG:
                    result = await self._send_log_notification(notification_data)
                elif channel == NotificationChannel.EMAIL:
                    result = await self._send_email_notification(notification_data)
                elif channel == NotificationChannel.WEBHOOK:
                    result = await self._send_webhook_notification(notification_data)
                elif channel == NotificationChannel.SLACK:
                    result = await self._send_slack_notification(notification_data)
                elif channel == NotificationChannel.DISCORD:
                    result = await self._send_discord_notification(notification_data)
                else:
                    result = {"success": False, "error": f"Unknown channel: {channel}"}
                
                results[channel.value] = result
                
            except Exception as e:
                logger.error(f"Failed to send notification via {channel.value}: {e}")
                results[channel.value] = {"success": False, "error": str(e)}
        
        return {
            "notification_id": notification_data["id"],
            "success": any(result.get("success", False) for result in results.values()),
            "results": results
        }
    
    async def _send_log_notification(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification via logging"""
        
        message = notification_data["message"]
        notification_type = notification_data["type"]
        metadata = notification_data["metadata"]
        
        log_message = f"NOTIFICATION: {message}"
        if metadata:
            log_message += f" | Metadata: {metadata}"
        
        if notification_type == NotificationType.CRITICAL.value:
            logger.critical(log_message)
        elif notification_type == NotificationType.ERROR.value:
            logger.error(log_message)
        elif notification_type == NotificationType.WARNING.value:
            logger.warning(log_message)
        elif notification_type == NotificationType.SUCCESS.value:
            logger.info(f"SUCCESS: {message}")
        else:
            logger.info(log_message)
        
        return {"success": True, "channel": "log"}
    
    async def _send_email_notification(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification via email"""
        
        # In real implementation, integrate with email service (SendGrid, AWS SES, etc.)
        logger.info(f"EMAIL notification would be sent: {notification_data['message']}")
        
        return {
            "success": True,
            "channel": "email",
            "note": "Email service not configured"
        }
    
    async def _send_webhook_notification(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification via webhook"""
        
        # In real implementation, send HTTP POST to configured webhook URL
        logger.info(f"WEBHOOK notification would be sent: {notification_data['message']}")
        
        return {
            "success": True,
            "channel": "webhook",
            "note": "Webhook service not configured"
        }
    
    async def _send_slack_notification(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification via Slack"""
        
        # In real implementation, integrate with Slack API
        logger.info(f"SLACK notification would be sent: {notification_data['message']}")
        
        return {
            "success": True,
            "channel": "slack",
            "note": "Slack integration not configured"
        }
    
    async def _send_discord_notification(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send notification via Discord"""
        
        # In real implementation, integrate with Discord webhooks
        logger.info(f"DISCORD notification would be sent: {notification_data['message']}")
        
        return {
            "success": True,
            "channel": "discord",
            "note": "Discord integration not configured"
        }
    
    async def notify_scraping_completed(
        self,
        job_id: str,
        movies_scraped: int,
        pages_processed: int,
        duration_minutes: float
    ) -> Dict[str, Any]:
        """Send notification when scraping job completes"""
        
        message = (
            f"Scraping job {job_id} completed successfully. "
            f"Scraped {movies_scraped} movies from {pages_processed} pages "
            f"in {duration_minutes:.1f} minutes."
        )
        
        metadata = {
            "job_id": job_id,
            "movies_scraped": movies_scraped,
            "pages_processed": pages_processed,
            "duration_minutes": duration_minutes,
            "event_type": "scraping_completed"
        }
        
        return await self.send_notification(
            message=message,
            notification_type=NotificationType.SUCCESS,
            metadata=metadata
        )
    
    async def notify_scraping_failed(
        self,
        job_id: str,
        error_message: str,
        pages_processed: int = 0
    ) -> Dict[str, Any]:
        """Send notification when scraping job fails"""
        
        message = (
            f"Scraping job {job_id} failed. "
            f"Error: {error_message}. "
            f"Processed {pages_processed} pages before failure."
        )
        
        metadata = {
            "job_id": job_id,
            "error_message": error_message,
            "pages_processed": pages_processed,
            "event_type": "scraping_failed"
        }
        
        return await self.send_notification(
            message=message,
            notification_type=NotificationType.ERROR,
            metadata=metadata
        )
    
    async def notify_download_completed(
        self,
        media_count: int,
        total_size_mb: float,
        failed_count: int = 0
    ) -> Dict[str, Any]:
        """Send notification when media download completes"""
        
        if failed_count > 0:
            message = (
                f"Media download completed with issues. "
                f"Successfully downloaded {media_count - failed_count} files "
                f"({total_size_mb:.1f} MB). {failed_count} downloads failed."
            )
            notification_type = NotificationType.WARNING
        else:
            message = (
                f"Media download completed successfully. "
                f"Downloaded {media_count} files ({total_size_mb:.1f} MB)."
            )
            notification_type = NotificationType.SUCCESS
        
        metadata = {
            "media_count": media_count,
            "total_size_mb": total_size_mb,
            "failed_count": failed_count,
            "event_type": "download_completed"
        }
        
        return await self.send_notification(
            message=message,
            notification_type=notification_type,
            metadata=metadata
        )
    
    async def notify_system_error(
        self,
        error_message: str,
        component: str,
        severity: str = "error"
    ) -> Dict[str, Any]:
        """Send notification for system errors"""
        
        message = f"System error in {component}: {error_message}"
        
        # Map severity to notification type
        severity_map = {
            "critical": NotificationType.CRITICAL,
            "error": NotificationType.ERROR,
            "warning": NotificationType.WARNING,
            "info": NotificationType.INFO
        }
        notification_type = severity_map.get(severity, NotificationType.ERROR)
        
        metadata = {
            "component": component,
            "error_message": error_message,
            "severity": severity,
            "event_type": "system_error"
        }
        
        return await self.send_notification(
            message=message,
            notification_type=notification_type,
            metadata=metadata
        )
    
    async def notify_storage_warning(
        self,
        storage_type: str,
        usage_percent: float,
        available_space_gb: float
    ) -> Dict[str, Any]:
        """Send notification for storage warnings"""
        
        message = (
            f"Storage warning: {storage_type} is {usage_percent:.1f}% full. "
            f"Available space: {available_space_gb:.1f} GB."
        )
        
        metadata = {
            "storage_type": storage_type,
            "usage_percent": usage_percent,
            "available_space_gb": available_space_gb,
            "event_type": "storage_warning"
        }
        
        notification_type = (
            NotificationType.CRITICAL if usage_percent > 95 
            else NotificationType.WARNING
        )
        
        return await self.send_notification(
            message=message,
            notification_type=notification_type,
            metadata=metadata
        )
    
    async def notify_rate_limit_exceeded(
        self,
        service: str,
        identifier: str,
        limit: int,
        window: str
    ) -> Dict[str, Any]:
        """Send notification for rate limit violations"""
        
        message = (
            f"Rate limit exceeded for {service}. "
            f"Identifier: {identifier}, Limit: {limit} requests per {window}."
        )
        
        metadata = {
            "service": service,
            "identifier": identifier,
            "limit": limit,
            "window": window,
            "event_type": "rate_limit_exceeded"
        }
        
        return await self.send_notification(
            message=message,
            notification_type=NotificationType.WARNING,
            metadata=metadata
        )
    
    async def notify_backup_completed(
        self,
        backup_type: str,
        backup_size_mb: float,
        backup_path: str
    ) -> Dict[str, Any]:
        """Send notification when backup completes"""
        
        message = (
            f"Backup completed: {backup_type}. "
            f"Size: {backup_size_mb:.1f} MB. "
            f"Location: {backup_path}"
        )
        
        metadata = {
            "backup_type": backup_type,
            "backup_size_mb": backup_size_mb,
            "backup_path": backup_path,
            "event_type": "backup_completed"
        }
        
        return await self.send_notification(
            message=message,
            notification_type=NotificationType.SUCCESS,
            metadata=metadata
        )
    
    async def get_notification_history(
        self,
        limit: int = 50,
        notification_type: Optional[NotificationType] = None
    ) -> List[Dict[str, Any]]:
        """Get notification history"""
        
        # In real implementation, this would query a database or log store
        # For now, return empty list
        logger.info(f"Retrieving notification history (limit: {limit})")
        
        return []
    
    async def test_notifications(self) -> Dict[str, Any]:
        """Test all enabled notification channels"""
        
        test_message = "This is a test notification from IMDb Scraper"
        test_metadata = {
            "test": True,
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "notification_test"
        }
        
        result = await self.send_notification(
            message=test_message,
            notification_type=NotificationType.INFO,
            metadata=test_metadata
        )
        
        logger.info("Notification test completed")
        return result
    
    async def configure_channels(self, channel_config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure notification channels"""
        
        # In real implementation, this would update database configuration
        logger.info(f"Configuring notification channels: {channel_config}")
        
        return {
            "success": True,
            "message": "Notification channels configured",
            "channels": channel_config
        }
    
    async def get_notification_settings(self) -> Dict[str, Any]:
        """Get current notification settings"""
        
        return {
            "enabled_channels": [channel.value for channel in self.enabled_channels],
            "notification_types": [ntype.value for ntype in NotificationType],
            "settings": {
                "email_enabled": False,
                "webhook_enabled": False,
                "slack_enabled": False,
                "discord_enabled": False,
                "log_enabled": True
            }
        }