import logging

from mappers.job_expander import _expand_jobs, _derive_horizon
from mappers.parse_evaluation_data import _parse_evaluation_metadata
from mappers.platform_mapper import _parse_platform, _extract_memory_nodes, _parse_comms
from mappers.request_config_mapper import _parse_config
from mappers.task_chain_mapper import _parse_task_chains
from mappers.task_template_mapper import _parse_task_templates, _map_tasks_to_domain_cores
from mappers.validators import _validate_jobs_have_eligible_cores
from schemas.schemas import ProblemInstance

logger = logging.getLogger(__name__)


class ProblemInstanceMapper:
    def from_request_json(self, data: dict) -> ProblemInstance:
        """
        Request JSON -> ProblemInstance.

        Important distinction:
        - tasks/dependencies/task_chains are templates.
        - jobs/job_dependencies are concrete finite-horizon schedulable instances.
        """
        comms_weight, mem_scale, max_jitter = _parse_config(data)

        clusters, cores = _parse_platform(data)
        memory_nodes = _extract_memory_nodes(
            data,
            cl_ids=[c.id for c in clusters],
        )

        comms = _parse_comms(data, core_ids={c.id for c in cores})

        tasks, dependencies = _parse_task_templates(data)
        tasks = _map_tasks_to_domain_cores(tasks, cores)

        task_chains = _parse_task_chains(
            data=data,
            tasks=tasks,
            dependencies=dependencies,
        )

        horizon = _derive_horizon(data, task_chains)

        jobs, job_dependencies = _expand_jobs(
            tasks=tasks,
            dependencies=dependencies,
            task_chains=task_chains,
            horizon=horizon,
        )

        evaluation = _parse_evaluation_metadata(data)

        _validate_jobs_have_eligible_cores(jobs)

        logger.info(
            (
                "Mapped problem | templates=%d | chains=%d | jobs=%d | "
                "template_deps=%d | job_deps=%d | cores=%d | clusters=%d | horizon=%s"
            ),
            len(tasks),
            len(task_chains),
            len(jobs),
            len(dependencies),
            len(job_dependencies),
            len(cores),
            len(clusters),
            horizon,
        )

        return ProblemInstance(
            tasks=tasks,
            dependencies=dependencies,
            task_chains=task_chains,
            jobs=jobs,
            job_dependencies=job_dependencies,
            clusters=clusters,
            cores=cores,
            memory_nodes=memory_nodes,
            communication_paths=comms,
            horizon=horizon,
            memory_penalty_scale=mem_scale,
            comms_penalty_weight=comms_weight,
            max_chain_jitter=max_jitter,
            evaluation=evaluation,
        )
