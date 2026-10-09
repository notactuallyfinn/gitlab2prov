import logging

from prov.model import ProvDocument

from gitlab2prov.adapters.git.fetcher import GitFetcher
from gitlab2prov.adapters.hub.fetcher import GithubFetcher
from gitlab2prov.adapters.lab.fetcher import GitlabFetcher
from gitlab2prov.domain.commands import (
    Combine,
    Fetch,
    Read,
    Serialize,
    Statistics,
    Transform,
    Write,
)
from gitlab2prov.prov import operations as ops
from gitlab2prov.prov.model import MODELS
from gitlab2prov.service_layer.unit_of_work import InMemoryUnitOfWork

log = logging.getLogger(__name__)


def fetch_git(cmd: Fetch, uow: InMemoryUnitOfWork, git_fetcher: GitFetcher) -> None:
    log.info(f"fetch {cmd=}")
    with git_fetcher as fetcher:
        fetcher.do_clone(cmd.url, cmd.token)
        with uow:
            for resource in fetcher.fetch_all():
                log.info(f"add {resource=}")
                uow.resources[cmd.url].add(resource)
        uow.commit()


def fetch_githosted(
    cmd: Fetch, uow: InMemoryUnitOfWork, githosted_fetcher: type[GithubFetcher | GitlabFetcher]
) -> None:
    log.info(f"fetch {cmd=}")
    fetcher = githosted_fetcher(cmd.token, cmd.url)
    with uow:
        for resource in fetcher.fetch_all():
            log.info(f"add {resource=}")
            uow.resources[cmd.url].add(resource)
        uow.commit()


def serialize(cmd: Serialize, uow: InMemoryUnitOfWork) -> ProvDocument:
    log.info(f"serialize graph consisting of {MODELS=}")
    document = ProvDocument()
    for prov_model in MODELS:
        log.info(f"populate {prov_model=}")
        provenance = prov_model(uow.resources[cmd.url])
        document = ops.combine(document, provenance)
        document = ops.dedupe(document)
    return document


def transform(cmd: Transform) -> ProvDocument:
    log.info(f"transform {cmd=}")
    if cmd.remove_duplicates:
        cmd.document = ops.dedupe(cmd.document)
    if cmd.use_pseudonyms:
        cmd.document = ops.pseudonymize(cmd.document)
    if cmd.merge_aliased_agents:
        cmd.document = ops.merge_duplicated_agents(cmd.document, cmd.merge_aliased_agents)
    return cmd.document


def combine(cmd: Combine) -> ProvDocument:
    log.info(f"combine {cmd=}")
    return ops.combine(*cmd.documents)


def write_file(cmd: Write) -> None:
    log.info(f"write {cmd=}")
    ops.write_provenance_file(cmd.document, cmd.filename, cmd.format)


def read_file(cmd: Read) -> ProvDocument:
    log.info(f"read {cmd=}")
    return ops.read_provenance_file(cmd.filename)


def statistics(cmd: Statistics) -> str:
    log.info(f"statistics {cmd=}")
    return ops.stats(cmd.document, cmd.resolution, cmd.format)


HANDLERS = {
    Fetch: [
        fetch_git,
        fetch_githosted,
    ],
    Serialize: [serialize],
    Read: [read_file],
    Write: [write_file],
    Combine: [combine],
    Transform: [transform],
    Statistics: [statistics],
}
