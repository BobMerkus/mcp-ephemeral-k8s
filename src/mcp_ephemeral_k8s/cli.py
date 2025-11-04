import logging
import sys
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    CliApp,
    CliPositionalArg,
    CliSubCommand,
    SettingsConfigDict,
)

from mcp_ephemeral_k8s.app.mcp_server import Transport, main

logger = logging.getLogger(__name__)


class Init(BaseModel):
    path: CliPositionalArg[Path] = Field(default_factory=Path.cwd)

    def cli_cmd(self) -> None:
        logger.info(f'Initializing MCP ephemeral K8s in path "{self.path}"')


class Serve(BaseModel):
    transport: Transport = Field(default="sse", description="The transport to use for the MCP ephemeral K8s client")
    namespace: str = Field(default="default", description="The namespace to use for the MCP ephemeral K8s client")
    allow_origins: list[str] | None = Field(default=["*"], description="The origins to allow CORS from")
    show_banner: bool = Field(default=True, description="Whether to show the banner")
    host: str = Field(default="127.0.0.1", description="The host to bind the server to")
    port: int = Field(default=8000, description="The port to bind the server to")

    def cli_cmd(self) -> None:
        logger.info(f'Serving MCP ephemeral K8s in namespace "{self.namespace}" on {self.host}:{self.port}')
        main(
            transport=self.transport,
            allow_origins=self.allow_origins,
            show_banner=self.show_banner,
            host=self.host,
            port=self.port,
        )


class McpEphemeralK8s(BaseSettings):
    """The MCP ephemeral K8s CLI."""

    model_config = SettingsConfigDict(cli_kebab_case=True)
    init: CliSubCommand[Init] = Field(description="Initialize the MCP ephemeral K8s client in the current directory")
    serve: CliSubCommand[Serve] = Field(description="Serve the MCP ephemeral K8s client")

    def cli_cmd(self) -> None:
        CliApp.run_subcommand(self)


def cli() -> None:
    if len(sys.argv) == 1:
        logger.error("No subcommand provided, defaulting to 'serve'")
        args = ["serve"]
    else:
        args = sys.argv[1:]

    result = CliApp.run(McpEphemeralK8s, cli_args=args).model_dump()
    logger.info(f"Result: {result}")
