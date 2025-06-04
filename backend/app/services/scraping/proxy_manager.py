"""
Proxy Manager - Handle proxy rotation and validation
"""

import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import random

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

@dataclass
class ProxyInfo:
    """Proxy information container"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"
    last_used: Optional[datetime] = None
    success_count: int = 0
    failure_count: int = 0
    avg_response_time: float = 0.0
    is_working: bool = True
    country: Optional[str] = None
    isp: Optional[str] = None

class ProxyManager:
    """Manage proxy rotation and validation"""
    
    def __init__(self):
        self.proxies: List[ProxyInfo] = []
        self.current_proxy_index = 0
        self.ipstack_api_key = settings.IPSTACK_API_KEY
        self.validation_cache = {}
        self.rotation_enabled = True
    
    def add_proxy(
        self, 
        host: str, 
        port: int, 
        username: str = None, 
        password: str = None,
        protocol: str = "http"
    ) -> None:
        """Add a proxy to the pool"""
        
        proxy = ProxyInfo(
            host=host,
            port=port,
            username=username,
            password=password,
            protocol=protocol
        )
        
        self.proxies.append(proxy)
        logger.info(f"Added proxy: {host}:{port}")
    
    def add_proxies_from_config(self, proxy_configs: List[Dict[str, Any]]) -> None:
        """Add multiple proxies from configuration"""
        
        for config in proxy_configs:
            self.add_proxy(
                host=config.get("host"),
                port=config.get("port"),
                username=config.get("username"),
                password=config.get("password"),
                protocol=config.get("protocol", "http")
            )
    
    def get_current_proxy(self) -> Optional[ProxyInfo]:
        """Get the current proxy"""
        
        if not self.proxies:
            return None
        
        working_proxies = [p for p in self.proxies if p.is_working]
        
        if not working_proxies:
            # Reset all proxies if none are working
            for proxy in self.proxies:
                proxy.is_working = True
            working_proxies = self.proxies
        
        if self.current_proxy_index >= len(working_proxies):
            self.current_proxy_index = 0
        
        return working_proxies[self.current_proxy_index]
    
    def rotate_proxy(self) -> Optional[ProxyInfo]:
        """Rotate to the next proxy"""
        
        if not self.rotation_enabled or len(self.proxies) <= 1:
            return self.get_current_proxy()
        
        working_proxies = [p for p in self.proxies if p.is_working]
        
        if len(working_proxies) <= 1:
            return self.get_current_proxy()
        
        self.current_proxy_index = (self.current_proxy_index + 1) % len(working_proxies)
        
        new_proxy = self.get_current_proxy()
        if new_proxy:
            logger.debug(f"Rotated to proxy: {new_proxy.host}:{new_proxy.port}")
        
        return new_proxy
    
    def get_proxy_url(self, proxy: ProxyInfo) -> str:
        """Generate proxy URL"""
        
        if proxy.username and proxy.password:
            return f"{proxy.protocol}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        else:
            return f"{proxy.protocol}://{proxy.host}:{proxy.port}"
    
    def get_proxy_dict(self, proxy: ProxyInfo) -> Dict[str, str]:
        """Get proxy dictionary for requests/aiohttp"""
        
        proxy_url = self.get_proxy_url(proxy)
        
        return {
            "http": proxy_url,
            "https": proxy_url
        }
    
    async def validate_proxy(self, proxy: ProxyInfo, timeout: int = 10) -> Dict[str, Any]:
        """Validate a single proxy"""
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            proxy_url = self.get_proxy_url(proxy)
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=timeout),
                connector=aiohttp.TCPConnector(ssl=False)
            ) as session:
                
                # Test basic connectivity
                async with session.get(
                    "http://httpbin.org/ip",
                    proxy=proxy_url
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        external_ip = data.get("origin", "").split(",")[0].strip()
                        
                        response_time = asyncio.get_event_loop().time() - start_time
                        
                        # Update proxy stats
                        proxy.success_count += 1
                        proxy.avg_response_time = (
                            (proxy.avg_response_time * (proxy.success_count - 1) + response_time) / 
                            proxy.success_count
                        )
                        proxy.is_working = True
                        proxy.last_used = datetime.utcnow()
                        
                        # Get geolocation info if ipstack API key is available
                        geo_info = {}
                        if self.ipstack_api_key and external_ip:
                            geo_info = await self._get_ip_geolocation(external_ip)
                            if geo_info:
                                proxy.country = geo_info.get("country_name")
                                proxy.isp = geo_info.get("connection", {}).get("isp")
                        
                        logger.info(f"Proxy {proxy.host}:{proxy.port} validated - IP: {external_ip}, Time: {response_time:.2f}s")
                        
                        return {
                            "valid": True,
                            "external_ip": external_ip,
                            "response_time": response_time,
                            "geolocation": geo_info
                        }
                    else:
                        raise aiohttp.ClientError(f"HTTP {response.status}")
                        
        except Exception as e:
            proxy.failure_count += 1
            proxy.is_working = False
            
            logger.warning(f"Proxy {proxy.host}:{proxy.port} validation failed: {str(e)}")
            
            return {
                "valid": False,
                "error": str(e),
                "response_time": asyncio.get_event_loop().time() - start_time
            }
    
    async def _get_ip_geolocation(self, ip_address: str) -> Dict[str, Any]:
        """Get IP geolocation using ipstack API"""
        
        if not self.ipstack_api_key:
            return {}
        
        # Check cache first
        if ip_address in self.validation_cache:
            cached_data = self.validation_cache[ip_address]
            if datetime.utcnow() - cached_data["timestamp"] < timedelta(hours=24):
                return cached_data["data"]
        
        try:
            url = f"http://api.ipstack.com/{ip_address}"
            params = {"access_key": self.ipstack_api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if "error" not in data:
                            # Cache the result
                            self.validation_cache[ip_address] = {
                                "data": data,
                                "timestamp": datetime.utcnow()
                            }
                            return data
                        else:
                            logger.warning(f"ipstack API error: {data['error']}")
                            
        except Exception as e:
            logger.error(f"Failed to get IP geolocation: {e}")
        
        return {}
    
    async def validate_all_proxies(self) -> Dict[str, Any]:
        """Validate all proxies in the pool"""
        
        if not self.proxies:
            return {"total": 0, "valid": 0, "invalid": 0, "results": []}
        
        logger.info(f"Validating {len(self.proxies)} proxies...")
        
        # Run validations concurrently
        tasks = [self.validate_proxy(proxy) for proxy in self.proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_count = sum(1 for result in results if isinstance(result, dict) and result.get("valid", False))
        invalid_count = len(results) - valid_count
        
        logger.info(f"Proxy validation completed: {valid_count} valid, {invalid_count} invalid")
        
        return {
            "total": len(self.proxies),
            "valid": valid_count,
            "invalid": invalid_count,
            "results": [
                {
                    "proxy": f"{proxy.host}:{proxy.port}",
                    "validation": result if isinstance(result, dict) else {"valid": False, "error": str(result)}
                }
                for proxy, result in zip(self.proxies, results)
            ]
        }
    
    def get_working_proxies(self) -> List[ProxyInfo]:
        """Get list of working proxies"""
        return [proxy for proxy in self.proxies if proxy.is_working]
    
    def get_proxy_statistics(self) -> Dict[str, Any]:
        """Get proxy pool statistics"""
        
        if not self.proxies:
            return {"total": 0, "working": 0, "failed": 0}
        
        working_proxies = self.get_working_proxies()
        
        total_success = sum(proxy.success_count for proxy in self.proxies)
        total_failures = sum(proxy.failure_count for proxy in self.proxies)
        
        avg_response_time = 0
        if working_proxies:
            avg_response_time = sum(proxy.avg_response_time for proxy in working_proxies) / len(working_proxies)
        
        countries = {}
        for proxy in working_proxies:
            if proxy.country:
                countries[proxy.country] = countries.get(proxy.country, 0) + 1
        
        return {
            "total": len(self.proxies),
            "working": len(working_proxies),
            "failed": len(self.proxies) - len(working_proxies),
            "total_requests": total_success + total_failures,
            "success_rate": total_success / (total_success + total_failures) if (total_success + total_failures) > 0 else 0,
            "avg_response_time": avg_response_time,
            "countries": countries,
            "rotation_enabled": self.rotation_enabled
        }
    
    def mark_proxy_failed(self, proxy: ProxyInfo, error: str = None) -> None:
        """Mark a proxy as failed"""
        
        proxy.failure_count += 1
        proxy.is_working = False
        
        logger.warning(f"Marked proxy {proxy.host}:{proxy.port} as failed. Error: {error}")
        
        # Auto-rotate to next proxy if current one failed
        if proxy == self.get_current_proxy():
            self.rotate_proxy()
    
    def mark_proxy_success(self, proxy: ProxyInfo, response_time: float = None) -> None:
        """Mark a proxy as successful"""
        
        proxy.success_count += 1
        proxy.is_working = True
        proxy.last_used = datetime.utcnow()
        
        if response_time:
            proxy.avg_response_time = (
                (proxy.avg_response_time * (proxy.success_count - 1) + response_time) / 
                proxy.success_count
            )
    
    def reset_proxy_stats(self) -> None:
        """Reset all proxy statistics"""
        
        for proxy in self.proxies:
            proxy.success_count = 0
            proxy.failure_count = 0
            proxy.avg_response_time = 0.0
            proxy.is_working = True
            proxy.last_used = None
        
        logger.info("Reset statistics for all proxies")
    
    def remove_failed_proxies(self) -> int:
        """Remove permanently failed proxies"""
        
        # Remove proxies with high failure rate
        failed_proxies = [
            proxy for proxy in self.proxies 
            if proxy.failure_count > 10 and proxy.failure_count > proxy.success_count * 3
        ]
        
        for proxy in failed_proxies:
            self.proxies.remove(proxy)
            logger.info(f"Removed failed proxy: {proxy.host}:{proxy.port}")
        
        return len(failed_proxies)
    
    def get_best_proxy(self) -> Optional[ProxyInfo]:
        """Get the best performing proxy"""
        
        working_proxies = self.get_working_proxies()
        
        if not working_proxies:
            return None
        
        # Score based on success rate and response time
        def calculate_score(proxy: ProxyInfo) -> float:
            total_requests = proxy.success_count + proxy.failure_count
            if total_requests == 0:
                return 0.5  # Neutral score for untested proxies
            
            success_rate = proxy.success_count / total_requests
            
            # Penalty for slow response times
            time_penalty = min(proxy.avg_response_time / 10.0, 1.0)  # Max penalty of 1.0
            
            return success_rate - time_penalty
        
        best_proxy = max(working_proxies, key=calculate_score)
        return best_proxy
    
    def enable_rotation(self) -> None:
        """Enable proxy rotation"""
        self.rotation_enabled = True
        logger.info("Proxy rotation enabled")
    
    def disable_rotation(self) -> None:
        """Disable proxy rotation"""
        self.rotation_enabled = False
        logger.info("Proxy rotation disabled")
    
    def get_random_proxy(self) -> Optional[ProxyInfo]:
        """Get a random working proxy"""
        
        working_proxies = self.get_working_proxies()
        
        if not working_proxies:
            return None
        
        return random.choice(working_proxies)
    
    async def test_proxy_with_target(self, proxy: ProxyInfo, target_url: str = "https://www.imdb.com") -> Dict[str, Any]:
        """Test proxy with specific target website"""
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            proxy_url = self.get_proxy_url(proxy)
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                connector=aiohttp.TCPConnector(ssl=False)
            ) as session:
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                
                async with session.get(
                    target_url,
                    proxy=proxy_url,
                    headers=headers
                ) as response:
                    
                    response_time = asyncio.get_event_loop().time() - start_time
                    
                    if response.status == 200:
                        content = await response.text()
                        
                        # Basic checks for successful access
                        success_indicators = ["imdb", "movies", "title"]
                        block_indicators = ["captcha", "blocked", "access denied", "robot"]
                        
                        has_success = any(indicator in content.lower() for indicator in success_indicators)
                        has_block = any(indicator in content.lower() for indicator in block_indicators)
                        
                        if has_success and not has_block:
                            self.mark_proxy_success(proxy, response_time)
                            
                            return {
                                "success": True,
                                "response_time": response_time,
                                "status_code": response.status,
                                "content_length": len(content),
                                "blocked": False
                            }
                        else:
                            return {
                                "success": False,
                                "response_time": response_time,
                                "status_code": response.status,
                                "blocked": has_block,
                                "error": "Content indicates blocking or unusual response"
                            }
                    else:
                        return {
                            "success": False,
                            "response_time": response_time,
                            "status_code": response.status,
                            "error": f"HTTP {response.status}"
                        }
                        
        except Exception as e:
            self.mark_proxy_failed(proxy, str(e))
            
            return {
                "success": False,
                "response_time": asyncio.get_event_loop().time() - start_time,
                "error": str(e)
            }
    
    def export_proxy_list(self, format: str = "json") -> str:
        """Export proxy list in specified format"""
        
        proxy_data = []
        for proxy in self.proxies:
            proxy_data.append({
                "host": proxy.host,
                "port": proxy.port,
                "username": proxy.username,
                "password": proxy.password,
                "protocol": proxy.protocol,
                "is_working": proxy.is_working,
                "success_count": proxy.success_count,
                "failure_count": proxy.failure_count,
                "avg_response_time": proxy.avg_response_time,
                "country": proxy.country,
                "isp": proxy.isp,
                "last_used": proxy.last_used.isoformat() if proxy.last_used else None
            })
        
        if format.lower() == "json":
            import json
            return json.dumps(proxy_data, indent=2)
        elif format.lower() == "csv":
            import csv
            import io
            
            output = io.StringIO()
            if proxy_data:
                writer = csv.DictWriter(output, fieldnames=proxy_data[0].keys())
                writer.writeheader()
                writer.writerows(proxy_data)
            
            return output.getvalue()
        else:
            # Plain text format
            lines = []
            for proxy in self.proxies:
                if proxy.username and proxy.password:
                    lines.append(f"{proxy.host}:{proxy.port}:{proxy.username}:{proxy.password}")
                else:
                    lines.append(f"{proxy.host}:{proxy.port}")
            
            return "\n".join(lines)
    
    def import_proxy_list(self, proxy_data: str, format: str = "txt") -> int:
        """Import proxy list from string data"""
        
        imported_count = 0
        
        try:
            if format.lower() == "json":
                import json
                proxies = json.loads(proxy_data)
                
                for proxy_info in proxies:
                    self.add_proxy(
                        host=proxy_info["host"],
                        port=proxy_info["port"],
                        username=proxy_info.get("username"),
                        password=proxy_info.get("password"),
                        protocol=proxy_info.get("protocol", "http")
                    )
                    imported_count += 1
            
            else:  # Plain text format
                lines = proxy_data.strip().split("\n")
                
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    parts = line.split(":")
                    if len(parts) >= 2:
                        host = parts[0]
                        port = int(parts[1])
                        username = parts[2] if len(parts) > 2 else None
                        password = parts[3] if len(parts) > 3 else None
                        
                        self.add_proxy(host, port, username, password)
                        imported_count += 1
            
            logger.info(f"Imported {imported_count} proxies")
            
        except Exception as e:
            logger.error(f"Failed to import proxy list: {e}")
        
        return imported_count
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on proxy pool"""
        
        health_status = {
            "status": "healthy",
            "total_proxies": len(self.proxies),
            "working_proxies": len(self.get_working_proxies()),
            "rotation_enabled": self.rotation_enabled,
            "current_proxy": None,
            "issues": []
        }
        
        if not self.proxies:
            health_status["status"] = "warning"
            health_status["issues"].append("No proxies configured")
        else:
            working_proxies = self.get_working_proxies()
            
            if not working_proxies:
                health_status["status"] = "critical"
                health_status["issues"].append("No working proxies available")
            elif len(working_proxies) < len(self.proxies) * 0.5:
                health_status["status"] = "degraded"
                health_status["issues"].append("More than 50% of proxies are not working")
            
            current_proxy = self.get_current_proxy()
            if current_proxy:
                health_status["current_proxy"] = f"{current_proxy.host}:{current_proxy.port}"
        
        return health_status