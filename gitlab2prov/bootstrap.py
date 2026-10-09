import inspect
import logging
from typing import Any, Callable

from gitlab2prov.adapters.git import GitFetcher
from gitlab2prov.adapters.hub import GithubFetcher
from gitlab2prov.adapters.lab import GitlabFetcher
from gitlab2prov.adapters.project_url import GithubProjectUrl, GitlabProjectUrl
from gitlab2prov.domain.commands import Command
from gitlab2prov.service_layer.handlers import HANDLERS
from gitlab2prov.service_layer.messagebus import MessageBus
from gitlab2prov.service_layer.unit_of_work import InMemoryUnitOfWork

log = logging.getLogger(__name__)


def bootstrap(
    platform: str,
    uow: InMemoryUnitOfWork = InMemoryUnitOfWork(),
    git_fetcher: type[GitFetcher] = GitFetcher,
    gitlab_fetcher: type[GitlabFetcher] = GitlabFetcher,
    github_fetcher: type[GithubFetcher] = GithubFetcher,
    github_url: type[GithubProjectUrl] = GithubProjectUrl,
    gitlab_url: type[GitlabProjectUrl] = GitlabProjectUrl,
) -> MessageBus:
    dependencies = {
        "uow": uow,
        "git_fetcher": git_fetcher(gitlab_url if platform == "gitlab" else github_url),
        "githosted_fetcher": gitlab_fetcher if platform == "gitlab" else github_fetcher,
    }
    injected_handlers = {
        command_type: [inject_dependencies(handler, dependencies) for handler in handlers]
        for command_type, handlers in HANDLERS.items()
    }

    return MessageBus(uow, handlers=injected_handlers)


def inject_dependencies(handler: Callable, dependencies: dict[str, Any]) -> Callable[[Command], Any]:
    params = inspect.signature(handler).parameters
    dependencies = {name: dependency for name, dependency in dependencies.items() if name in params}
    for name, dep in dependencies.items():
        log.debug(f"inject dependency {dep} into handler {handler} as param {name}")
    return lambda cmd: handler(cmd, **dependencies)
