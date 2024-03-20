# %%
import argparse
import json
import re
from pathlib import Path
from typing import List, Union

import requests
from user_agents.parsers import UserAgent, parse


class UserAgentUpdater:
    UPDATE_USERAGENT_URL = r"https://user-agents.net/download"
    USERAGENT_VERSION_URL = r"https://www.browsers.fyi/api/"

    def __init__(
        self,
        output_folder: Union[str, Path],
        timeout: float = 4.0,
        output_name: str = "browsers.json",
    ):
        self.timeout = timeout
        self.ua_list = []
        self.output_name = output_name

        if isinstance(output_folder, str):
            output_folder = Path(output_folder)
        if not output_folder.exists():
            raise NameError("The specified folder does not exist.")
        if not output_folder.is_dir():
            raise TypeError("The specified path should be a folder.")
        self.output_folder = output_folder

        # Regex patterns
        self.chrome_pattern = re.compile(r"chrome", re.IGNORECASE)
        self.firefox_pattern = re.compile(r"firefox", re.IGNORECASE)
        self.safari_pattern = re.compile(r"safari", re.IGNORECASE)
        self.edge_pattern = re.compile(r"edge", re.IGNORECASE)

        self.ios_pattern = re.compile(r"ios", re.IGNORECASE)
        self.linux_pattern = re.compile(
            r"Linux|Ubuntu|Arch|Fedora|OpenSuse|Debian", re.IGNORECASE
        )
        self.macos_pattern = re.compile(r"Mac", re.IGNORECASE)
        self.windows_pattern = re.compile(r"Windows|win10|win11|win7", re.IGNORECASE)
        self.android_pattern = re.compile(r"android", re.IGNORECASE)

    def send_get_request(self, url: str):
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        result = response.text
        return json.loads(result)

    def send_post_request(self, url: str, query_parameters: dict):
        response = requests.post(url, data=query_parameters, timeout=self.timeout)
        response.raise_for_status()
        result = response.text
        return json.loads(result)
    
    def send_version_request(self, browser:str):

    def send_user_agent_request(
        self,
        browser: str = "chrome",
        version: Union[float, None] = None,
        limit: int = 100,
    ) -> List[str]:
        """
        Send an API request to get the specified user agents.
        """
        if not version:
            # get the current version for the given browser using API request
            current_browser_versions = self.send_get_request(self.USERAGENT_VERSION_URL)
            version = current_browser_versions.get(browser).get("version")
            if not version:
                version = 0.0
            if isinstance(version,str):
                try:
                    version = float(version)
                except TypeError as e:
                    print(e)
                except ValueError as e:
                    print(e)

        if re.search(self.safari_pattern, browser):
            # retrieving Safari user agents works differently
            return self._send_safari_request(version=version, limit=limit)

        input_query_parameters = {
            "browser": browser,
            "version": str(version),
            "limit": str(limit),
            "download": "json",
        }
        user_agents = self.send_post_request(
            self.UPDATE_USERAGENT_URL, input_query_parameters
        )
        return user_agents
    def _test_safari_parsing(self, file_path:str, version: float) -> List[str]:
        with open(file_path) as f:
            ua_str_list = json.load(f)
        all_safari_user_agents = self.parse_user_agents(ua_str_list)

        # check the versions
        correct_safari_user_agents = []
        for ua_str in all_safari_user_agents:
            ua_dict = json.loads(ua_str)
            version_ua_str = ua_dict.get("version")
            browser_ua_str = ua_dict.get("browser")
            if isinstance(version_ua_str,float) and version_ua_str>=version and browser_ua_str=="safari":
                    correct_safari_user_agents.append(ua_str)

        return correct_safari_user_agents

    def _send_safari_request(self, version: float, limit: int) -> List[str]:
        """
        Unfortunately, we need a different approach for Safari
        user agents as the API does not work well with Safari
        versions. This method downloads the complete Safari list and
        does it's own version selection.
        """

        input_query_parameters = {
            "browser": "safari",
            "browser_type": "browser",
            "download": "json",
        }
        all_safari_user_agents = self.send_post_request(
            self.UPDATE_USERAGENT_URL, input_query_parameters
        )
        all_safari_user_agents = self.parse_user_agents(all_safari_user_agents)

        # check the versions and browser type
        correct_safari_user_agents = []
        for ua_str in all_safari_user_agents:
            ua_dict = json.loads(ua_str)
            version_ua_str = ua_dict.get("version")
            browser_ua_str = ua_dict.get("browser")
            if isinstance(version_ua_str,float) and version_ua_str>=version and browser_ua_str=="safari":
                    correct_safari_user_agents.append(ua_str)
                    
        return correct_safari_user_agents

    def parse_user_agents(
        self, user_agents: List[str], remember: bool = False
    ) -> List[str]:
        """
        Parse a list of user agents strings. If rember is true,
        add the user agents to memory so they can be written
        using the write_useragents() method.
        """
        parsed_user_agents = []

        for user_agent_string in user_agents:
            try:
                # replace extra info between square brackets
                # (usually ip adress) and slashes
                user_agent_string = re.sub(r"\[.*?\]|\\", "", user_agent_string)
                user_agent_string = user_agent_string.strip()

                # retrieve all the info we need from the user agent string
                user_agent = parse(user_agent_string)
                platform = self._get_platform(user_agent)
                browser = self._get_browser(user_agent)
                version = self._get_version(user_agent)
                os = self._get_os(user_agent)
                system = " ".join(
                    [user_agent.browser.family, str(version), user_agent.os.family]
                )
                ua_parsed = str(
                    json.dumps(
                        {
                            "useragent": user_agent_string,
                            "percent": 100.0,
                            "type": platform,
                            "system": system,
                            "browser": browser,
                            "version": version,
                            "os": os,
                        }
                    )
                )

                parsed_user_agents.append(ua_parsed)
            except Exception as e:
                # we don't want to log these exceptions,
                # as there may be many user agents that
                # cannot be correctly parsed.
                continue

        if remember:
            # rember the user agents for next write
            self.ua_list.extend(parsed_user_agents)

        return parsed_user_agents

    def write_useragents(self) -> None:
        """
        Write all the user agents to disk at the specified path.
        """
        full_path = self.output_folder.joinpath(self.output_name)

        # Check that some user agents have been found before writing.
        if len(self.ua_list) > 0:
            with open(full_path, "w") as writer:
                writer.write("\n".join(self.ua_list))

    @staticmethod
    def _get_platform(user_agent: UserAgent):
        """
        Get the platform as a string.
        """
        if user_agent.is_mobile:
            return "mobile"
        elif user_agent.is_tablet:
            return "tablet"
        elif user_agent.is_pc:
            return "pc"
        elif user_agent.is_bot:
            return "bot"
        else:
            return "other"

    def _get_browser(self, user_agent: UserAgent) -> str:
        """
        Get the browser as a user friendly string.
        """
        browser = user_agent.browser.family

        if re.search(self.chrome_pattern, browser):
            return "chrome"
        elif re.search(self.firefox_pattern, browser):
            return "firefox"
        elif re.search(self.safari_pattern, browser):
            return "safari"
        elif re.search(self.edge_pattern, browser):
            return "edge"

        return browser

    def _get_os(self, user_agent: UserAgent) -> str:
        """
        Get the operating system as a user friendly string.
        """
        os = user_agent.os.family
        if re.search(self.ios_pattern, os):
            return "ios"
        elif re.search(self.linux_pattern, os):
            return "linux"
        elif re.search(self.macos_pattern, os):
            return "macos"
        elif re.search(self.windows_pattern, os):
            return "win10"
        elif re.search(self.android_pattern, os):
            return "android"

        return os

    def _get_version(self, user_agent: UserAgent) -> float:
        version = user_agent.browser.version
        if len(version) > 1:
            return float(str(version[0]) + "." + str(version[1]))
        elif len(version) == 1:
            return float(version[0])
        else:
            return float(version)


# %%
if __name__ == "__main__":
    updater = UserAgentUpdater(".")

    # Parse the command line arguments, if provided.
    parser = argparse.ArgumentParser(
        description="Script to update the list of user agents."
    )
    parser.add_argument(
        "browser_args",
        nargs="*",
        default=[],
        help="Arbitrary number of browsers to include in the update",
    )
    parser.add_argument(
        "--limit",
        default=100,
        type=int,
        help="The max number of user agents per browser",
    )
    args = parser.parse_args()
    possible_browsers = [
        "chrome",
        "edge",
        "safari",
        "firefox",
        "opera",
        "samsung-browser",
    ]
    requested_browsers = [
        browser for browser in args.browser_args if browser in possible_browsers
    ]

    if len(requested_browsers) > 0:
        for requested_browser in requested_browsers:
            new_useragents = updater.send_user_agent_request(
                requested_browser, limit=args["limit"]
            )
            updater.parse_user_agents(new_useragents, remember=True)

    else:
        # If no comment line arguments are given (so if you just run this script),
        # update the user agent list with some default values.
        # new_firefox_useragents = updater.send_user_agent_request("firefox", limit=100)
        # updater.parse_user_agents(new_firefox_useragents, remember=True)
        new_safari_useragents = updater.send_user_agent_request("safari", limit=100)
        updater.parse_user_agents(new_safari_useragents, remember=True)
        # new_edge_useragents = updater.send_user_agent_request("edge", limit=100)
        # updater.parse_user_agents(new_edge_useragents, remember=True)
        # new_chrome_useragents = updater.send_user_agent_request("chrome", limit=100)
        # updater.parse_user_agents(new_chrome_useragents, remember=True)

    # write the new user agents to disk
    updater.write_useragents()


# %%
