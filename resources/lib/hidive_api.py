import requests
import xbmc
from typing import Optional, Dict, Any, List
import uuid


class HidiveAPI:
    """
    HiDive API client with improved functional design.
    Reduces mutable state and provides clearer error handling.
    """

    def __init__(self, username: str, password: str, debug_enabled: bool = False):
        self._base_url = "https://dce-frontoffice.imggaming.com/api"
        self._session = self._create_session()
        self._username = username
        self._password = password
        self._auth_token: Optional[str] = None
        self._debug_enabled = debug_enabled

    def _create_session(self) -> requests.Session:
        """
        Private method to create a configured session.

        Returns:
            requests.Session: Configured session with headers
        """
        session = requests.Session()
        session.headers.update({
            "X-Api-Key": "f086d846-37ed-4761-99ac-e538c03e5701",
            "X-App-Var": "2.5.1",
            "User-Agent": "HIDIVE/126 CFNetwork/1496.0.7 Darwin/23.5.0",
            "realm": "dce.hidive",
            "X-Device-Id": "iPhone16,2",
            "Content-Type": "application/json"
        })
        return session

    def _make_get_request(self, url: str, operation_name: str) -> Optional[Dict[str, Any]]:
        """
        Private helper method to make GET requests with consistent logging and error handling.

        Args:
            url: URL to make the request to
            operation_name: Name of the operation for logging

        Returns:
            Optional[Dict[str, Any]]: Response JSON or None on error
        """
        from utils import log_api_response

        xbmc.log(f"HIDIVE: {operation_name} with URL: {url}", level=xbmc.LOGINFO)
        try:
            response = self._session.get(url)
            response.raise_for_status()
            response_data = response.json()

            # Log API response if debug is enabled
            log_api_response(operation_name, response_data, self._debug_enabled)

            return response_data
        except requests.exceptions.RequestException as e:
            xbmc.log(f"HIDIVE: Failed to {operation_name.lower()}: {e}", level=xbmc.LOGERROR)
            return None

    def _make_post_request(self, url: str, payload: Dict[str, Any],
                          operation_name: str) -> Optional[Dict[str, Any]]:
        """
        Private helper method to make POST requests with consistent logging and error handling.

        Args:
            url: URL to make the request to
            payload: JSON payload for the request
            operation_name: Name of the operation for logging

        Returns:
            Optional[Dict[str, Any]]: Response JSON or None on error
        """
        from utils import log_api_response

        xbmc.log(f"HIDIVE: {operation_name} with URL: {url}", level=xbmc.LOGINFO)
        try:
            response = self._session.post(url, json=payload)
            response.raise_for_status()
            response_data = response.json()

            # Log API response if debug is enabled
            log_api_response(operation_name, response_data, self._debug_enabled)

            return response_data
        except requests.exceptions.RequestException as e:
            xbmc.log(f"HIDIVE: Failed to {operation_name.lower()}: {e}", level=xbmc.LOGERROR)
            return None

    def is_authenticated(self) -> bool:
        """
        Check if the session is authenticated.

        Returns:
            bool: True if authenticated
        """
        return 'Authorization' in self._session.headers

    def set_auth_token(self, token: str) -> None:
        """
        Set the authentication token for the session.

        Args:
            token: Authentication token
        """
        self._session.headers.update({"Authorization": f"Bearer {token}"})
        self._auth_token = token

    def clear_auth_token(self) -> None:
        """
        Clear the authentication token from the session.
        """
        if 'Authorization' in self._session.headers:
            del self._session.headers['Authorization']
        self._auth_token = None

    def login(self) -> bool:
        """
        Authenticate with HiDive API.

        Returns:
            bool: True if login successful
        """
        if self.is_authenticated() and self._auth_token:
            return True

        if not self._username or not self._password:
            return False

        url = f"{self._base_url}/v2/login"
        payload = {"id": self._username, "secret": self._password}

        response_data = self._make_post_request(url, payload, "Login request")
        if response_data:
            token = response_data.get("authorisationToken")
            if token:
                self.set_auth_token(token)
                return True
        return False

    def get_profiles(self) -> Optional[List[Dict[str, Any]]]:
        """
        Get user profiles from HiDive API.

        Returns:
            Optional[List[Dict[str, Any]]]: List of profiles or None on error
        """
        url = f"{self._base_url}/v1/profile"
        response_data = self._make_get_request(url, "Getting profiles")
        return response_data.get("items", []) if response_data else None

    def activate_profile(self, profile_id: str) -> Optional[str]:
        """
        Activate a user profile.

        Args:
            profile_id: ID of the profile to activate

        Returns:
            Optional[str]: New auth token or None on error
        """
        url = f"{self._base_url}/v1/profile/{profile_id}"
        payload = {"profileId": profile_id}

        response_data = self._make_post_request(url, payload, "Activating profile")
        if response_data:
            new_token = response_data.get("authToken")
            if new_token:
                self.set_auth_token(new_token)
                return new_token
        return None

    def get_watchlists(self, last_seen: Optional[str] = None, entries_per_page: int = 25) -> Optional[Dict[str, Any]]:
        """
        Get user watchlists from HiDive API with pagination support.

        Args:
            last_seen: Last seen parameter for pagination
            entries_per_page: Number of entries per page (rpp parameter)

        Returns:
            Optional[Dict[str, Any]]: Watchlists data or None on error
        """
        # Use basic endpoint without rpp parameter as it may not be supported for watchlists list
        url = f"{self._base_url}/v3/user/watchlist"
        if last_seen:
            url += f"?lastSeen={last_seen}"

        return self._make_get_request(url, "Getting watchlists")

    def get_watchlist(self) -> Optional[Dict[str, Any]]:
        """
        Get user watchlist from HiDive API (legacy method for backward compatibility).

        Returns:
            Optional[Dict[str, Any]]: Watchlist data or None on error
        """
        return self.get_watchlists()

    def get_watchlist_content(self, watchlist_id: str, last_seen: Optional[str] = None,
                             entries_per_page: int = 20, enable_pagination: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get content from a specific watchlist with pagination support.

        Args:
            watchlist_id: ID of the watchlist
            last_seen: Last seen parameter for pagination
            entries_per_page: Number of entries per page (for pagination only)
            enable_pagination: Whether to fetch all pages

        Returns:
            Optional[Dict[str, Any]]: Watchlist content data or None on error
        """
        # Build URL without rpp parameter initially (may not be supported)
        url = f"{self._base_url}/v4/user/watchlist/{watchlist_id}"
        if last_seen:
            url += f"?lastSeen={last_seen}"

        # Get initial watchlist content
        watchlist_data = self._make_get_request(url, f"Getting watchlist content ({watchlist_id})")
        if not watchlist_data:
            return None

        # Handle pagination if enabled
        if enable_pagination and watchlist_data.get('paging', {}).get('moreDataAvailable', False):
            watchlist_data = self._paginate_watchlist_content(watchlist_data, watchlist_id, entries_per_page)

        return watchlist_data

    def _paginate_watchlist_content(self, initial_data: Dict[str, Any], watchlist_id: str,
                                   entries_per_page: int) -> Dict[str, Any]:
        """
        Private method to paginate watchlist content.

        Args:
            initial_data: Initial watchlist response
            watchlist_id: ID of the watchlist
            entries_per_page: Number of entries per page

        Returns:
            Dict[str, Any]: Complete watchlist data with all pages
        """
        max_pages = 10  # Safety limit
        current_page = 0
        all_content = initial_data.get('content', [])
        current_paging = initial_data.get('paging', {})

        while (current_page < max_pages and
               current_paging.get('moreDataAvailable', False)):

            try:
                last_seen = current_paging.get('lastSeen', '')
                if not last_seen:
                    break

                # Use only lastSeen for pagination (rpp not supported for watchlists)
                url = (f"{self._base_url}/v4/user/watchlist/{watchlist_id}"
                      f"?lastSeen={last_seen}")

                page_data = self._make_get_request(url, f"Getting watchlist page {current_page + 1}")
                if page_data and 'content' in page_data:
                    all_content.extend(page_data['content'])
                    current_paging = page_data.get('paging', {})
                else:
                    break

                current_page += 1

            except Exception as e:
                if self._debug_enabled:
                    try:
                        import xbmc
                        xbmc.log(f"HIDIVE: Error paginating watchlist content: {e}", level=xbmc.LOGERROR)
                    except ImportError:
                        pass
                break

        # Update the initial data with all content
        initial_data['content'] = all_content
        initial_data['paging'] = current_paging

        return initial_data

    def get_dashboard(self, buckets_count: int = 10, entries_per_bucket: int = 25,
                     enable_pagination: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get dashboard content from HiDive API with configurable parameters and pagination support.

        Args:
            buckets_count: Number of buckets to request (bpp parameter)
            entries_per_bucket: Number of entries per bucket (rpp parameter)
            enable_pagination: Whether to fetch all pages using pagination

        Returns:
            Optional[Dict[str, Any]]: Dashboard data or None on error
        """
        # Use the same parameters as Artemis app for compatibility
        base_params = {
            'bpp': buckets_count,
            'rpp': entries_per_bucket,
            'displaySectionLinkBuckets': 'SHOW',
            'displayEpgBuckets': 'HIDE',
            'displayEmptyBucketShortcuts': 'SHOW',
            'displayContentAvailableOnSignIn': 'SHOW',
            'displayGeoblocked': 'HIDE',
            'bspp': buckets_count
        }

        # Build query string
        query_params = '&'.join([f"{k}={v}" for k, v in base_params.items()])
        url = f"{self._base_url}/v4/content/home?{query_params}"

        # Get initial dashboard data
        dashboard_data = self._make_get_request(url, "Getting dashboard")
        if not dashboard_data:
            return None

        # Handle pagination if enabled
        if enable_pagination:
            dashboard_data = self._paginate_dashboard_buckets(dashboard_data, entries_per_bucket)

        # Log dashboard response for debugging
        if self._debug_enabled:
            try:
                import xbmc
                bucket_count = len(dashboard_data.get('buckets', []))
                total_items = sum(len(bucket.get('contentList', []))
                                for bucket in dashboard_data.get('buckets', []))
                xbmc.log(f"HIDIVE: Dashboard API response - {bucket_count} buckets, {total_items} total items",
                        level=xbmc.LOGINFO)
            except ImportError:
                pass

        return dashboard_data

    def get_dashboard_safe(self, buckets_count: int = 10, entries_per_bucket: int = 25) -> Optional[Dict[str, Any]]:
        """
        Get dashboard content with memory-safe processing for Kodi.
        This method uses conservative parameters to prevent crashes.

        Args:
            buckets_count: Number of buckets to request (max 10 for API compatibility)
            entries_per_bucket: Number of entries per bucket (max 50 for safety)

        Returns:
            Optional[Dict[str, Any]]: Dashboard data or None on error
        """
        # Enforce safety limits based on API constraints
        safe_buckets_count = min(buckets_count, 10)  # API limit appears to be 10
        safe_entries_per_bucket = min(entries_per_bucket, 25)  # Conservative limit

        if self._debug_enabled:
            try:
                import xbmc
                xbmc.log(f"HIDIVE: Getting dashboard with safe limits - buckets: {safe_buckets_count}, "
                        f"entries per bucket: {safe_entries_per_bucket}", level=xbmc.LOGINFO)
            except ImportError:
                pass

        try:
            # Get dashboard with conservative parameters
            dashboard_data = self.get_dashboard(
                buckets_count=safe_buckets_count,
                entries_per_bucket=safe_entries_per_bucket,
                enable_pagination=False
            )

            return dashboard_data

        except Exception as e:
            if self._debug_enabled:
                try:
                    import xbmc
                    xbmc.log(f"HIDIVE: Error in get_dashboard_safe: {e}", level=xbmc.LOGERROR)
                except ImportError:
                    pass
            # Fallback to minimal dashboard request
            return self.get_dashboard(buckets_count=5, entries_per_bucket=10, enable_pagination=False)

    def get_video_data(self, video_id: str, language: str = 'eng') -> Optional[Dict[str, Any]]:
        """
        Get video metadata from HiDive API.

        Args:
            video_id: ID of the video
            language: Language code for the video

        Returns:
            Optional[Dict[str, Any]]: Video data or None on error
        """
        session_id = str(uuid.uuid4())
        url = f"{self._base_url}/v2/download/vod/{video_id}/HIGH/{language}?sessionId={session_id}"
        return self._make_get_request(url, "Getting video data")

    def get_stream_from_callback(self, callback_url: str) -> Optional[Dict[str, Any]]:
        """
        Get stream data from callback URL.

        Args:
            callback_url: Callback URL from video metadata

        Returns:
            Optional[Dict[str, Any]]: Stream data or None on error
        """
        return self._make_get_request(callback_url, "Getting stream from callback")

    def _paginate_dashboard_buckets(self, dashboard_data: Dict[str, Any],
                                   entries_per_bucket: int) -> Dict[str, Any]:
        """
        Private method to handle dashboard bucket pagination like Artemis app.

        Args:
            dashboard_data: Initial dashboard response
            entries_per_bucket: Number of entries per bucket for pagination

        Returns:
            Dict[str, Any]: Dashboard data with paginated buckets
        """
        if not dashboard_data or 'buckets' not in dashboard_data:
            return dashboard_data

        try:
            for bucket in dashboard_data.get('buckets', []):
                if bucket.get('paging', {}).get('moreDataAvailable', False):
                    self._paginate_bucket_content(bucket, entries_per_bucket)
        except Exception as e:
            if self._debug_enabled:
                try:
                    import xbmc
                    xbmc.log(f"HIDIVE: Error during bucket pagination: {e}", level=xbmc.LOGERROR)
                except ImportError:
                    pass

        return dashboard_data

    def _paginate_bucket_content(self, bucket: Dict[str, Any], entries_per_bucket: int) -> None:
        """
        Private method to paginate content within a specific bucket.

        Args:
            bucket: Bucket data to paginate
            entries_per_bucket: Number of entries per page
        """
        if not bucket or 'paging' not in bucket:
            return

        max_pages = 5  # Safety limit to prevent infinite loops
        current_page = 0

        while (current_page < max_pages and
               bucket.get('paging', {}).get('moreDataAvailable', False)):

            try:
                last_seen = bucket['paging'].get('lastSeen', '')
                if not last_seen:
                    break

                # Build pagination URL
                bucket_type = bucket.get('type', '')
                bucket_exid = bucket.get('exid', '')

                if bucket_type and bucket_exid:
                    url = (f"{self._base_url}/v4/content/bucket/{bucket_type}/{bucket_exid}"
                          f"?lastSeen={last_seen}&rpp={entries_per_bucket}")

                    page_data = self._make_get_request(url, f"Getting bucket page {current_page + 1}")
                    if page_data and 'contentList' in page_data:
                        # Append new content to existing content
                        bucket['contentList'].extend(page_data['contentList'])

                        # Update paging info
                        bucket['paging'] = page_data.get('paging', {})
                    else:
                        break
                else:
                    break

                current_page += 1

            except Exception as e:
                if self._debug_enabled:
                    try:
                        import xbmc
                        xbmc.log(f"HIDIVE: Error paginating bucket content: {e}", level=xbmc.LOGERROR)
                    except ImportError:
                        pass
                break

    def get_series(self, series_id: str) -> Optional[Dict[str, Any]]:
        """
        Get series data from HiDive API.

        Args:
            series_id: ID of the series

        Returns:
            Optional[Dict[str, Any]]: Series data or None on error
        """
        url = f"{self._base_url}/v4/series/{series_id}?rpp=25"
        return self._make_get_request(url, "Getting series")

    def get_season(self, season_id: str) -> Optional[Dict[str, Any]]:
        """
        Get season data from HiDive API.

        Args:
            season_id: ID of the season

        Returns:
            Optional[Dict[str, Any]]: Season data or None on error
        """
        url = f"{self._base_url}/v4/season/{season_id}?rpp=25"
        return self._make_get_request(url, "Getting season")

    def get_playlist(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """
        Get playlist data from HiDive API.

        Args:
            playlist_id: ID of the playlist

        Returns:
            Optional[Dict[str, Any]]: Playlist data or None on error
        """
        url = f"{self._base_url}/v4/playlist/{playlist_id}?rpp=25"
        return self._make_get_request(url, "Getting playlist")

    def get_bucket_content(self, bucket_type: str, bucket_exid: str,
                          entries_per_page: int = 25, last_seen: Optional[str] = None,
                          enable_pagination: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get content from a specific bucket with pagination support.

        Args:
            bucket_type: Type of the bucket
            bucket_exid: External ID of the bucket
            entries_per_page: Number of entries per page
            last_seen: Last seen parameter for pagination
            enable_pagination: Whether to fetch all pages

        Returns:
            Optional[Dict[str, Any]]: Bucket content data or None on error
        """
        # Build URL with pagination parameters
        url = f"{self._base_url}/v4/content/bucket/{bucket_type}/{bucket_exid}?rpp={entries_per_page}"
        if last_seen:
            url += f"&lastSeen={last_seen}"

        # Get initial bucket data
        bucket_data = self._make_get_request(url, f"Getting bucket content ({bucket_type})")
        if not bucket_data:
            return None

        # Handle pagination if enabled
        if enable_pagination and bucket_data.get('paging', {}).get('moreDataAvailable', False):
            bucket_data = self._paginate_single_bucket(bucket_data, bucket_type, bucket_exid, entries_per_page)

        return bucket_data

    def _paginate_single_bucket(self, initial_data: Dict[str, Any], bucket_type: str,
                               bucket_exid: str, entries_per_page: int) -> Dict[str, Any]:
        """
        Private method to paginate a single bucket's content.

        Args:
            initial_data: Initial bucket response
            bucket_type: Type of the bucket
            bucket_exid: External ID of the bucket
            entries_per_page: Number of entries per page

        Returns:
            Dict[str, Any]: Complete bucket data with all pages
        """
        max_pages = 10  # Safety limit
        current_page = 0
        all_content = initial_data.get('contentList', [])
        current_paging = initial_data.get('paging', {})

        while (current_page < max_pages and
               current_paging.get('moreDataAvailable', False)):

            try:
                last_seen = current_paging.get('lastSeen', '')
                if not last_seen:
                    break

                url = (f"{self._base_url}/v4/content/bucket/{bucket_type}/{bucket_exid}"
                      f"?lastSeen={last_seen}&rpp={entries_per_page}")

                page_data = self._make_get_request(url, f"Getting bucket page {current_page + 1}")
                if page_data and 'contentList' in page_data:
                    all_content.extend(page_data['contentList'])
                    current_paging = page_data.get('paging', {})
                else:
                    break

                current_page += 1

            except Exception as e:
                if self._debug_enabled:
                    try:
                        import xbmc
                        xbmc.log(f"HIDIVE: Error paginating single bucket: {e}", level=xbmc.LOGERROR)
                    except ImportError:
                        pass
                break

        # Update the initial data with all content
        initial_data['contentList'] = all_content
        initial_data['paging'] = current_paging

        return initial_data

    def search(self, query: str, hits_per_page: int = 10) -> Optional[Dict[str, Any]]:
        """
        Search for content using HiDive's Algolia search endpoint.

        Args:
            query: Search query string
            hits_per_page: Number of results per page (default: 10, max: 20)

        Returns:
            Optional[Dict[str, Any]]: Search results or None on error
        """
        if not query or not query.strip():
            return None

        # Limit hits per page to reasonable bounds
        hits_per_page = min(max(hits_per_page, 1), 20)

        # Algolia search endpoint used by HiDive
        search_url = ("https://h99xldr8mj-dsn.algolia.net/1/indexes/*/queries"
                     "?x-algolia-agent=Algolia%20for%20JavaScript%20(3.35.1)%3B%20Browser"
                     "&x-algolia-application-id=H99XLDR8MJ"
                     "&x-algolia-api-key=e55ccb3db0399eabe2bfc37a0314c346")

        # URL encode the query
        try:
            import urllib.parse
            encoded_query = urllib.parse.quote(query.strip(), safe='')
        except ImportError:
            # Fallback for older Python versions
            encoded_query = query.strip().replace(' ', '%20')

        # Build search payload for both series and playlists
        payload = {
            "requests": [
                {
                    "indexName": "prod-dce.hidive-livestreaming-events",
                    "params": f"query={encoded_query}&facetFilters=%5B%22type%3AVOD_SERIES%22%5D&hitsPerPage={hits_per_page}"
                },
                {
                    "indexName": "prod-dce.hidive-livestreaming-events",
                    "params": f"query={encoded_query}&facetFilters=%5B%22type%3AVOD_PLAYLIST%22%5D&hitsPerPage={hits_per_page}"
                }
            ]
        }

        return self._make_post_request(search_url, payload, "Searching content")
