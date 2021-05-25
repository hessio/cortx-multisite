#
# Copyright (c) 2021 Seagate Technology LLC and/or its Affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# For any questions about this software or licensing,
# please email opensource@seagate.com or cortx-questions@seagate.com.
#

import asyncio
from aiohttp import web
import json
import logging
from s3replicationcommon.jobs import Jobs
from s3replicationcommon.job import JobJsonEncoder
from s3replicationcommon.job import ReplicationJobRecordKey
from .transfer_initiator import TransferInitiator

_logger = logging.getLogger('s3replicator')

# Route table declaration
routes = web.RouteTableDef()


@routes.get('/jobs')  # noqa: E302
async def list_jobs(request):
    """List_jobs
    Handler to list in-progress jobs
    """
    jobs = request.app['all_jobs']

    _logger.debug('Number of jobs in-progress {}'.format(jobs.count()))
    # _logger.debug('List of jobs in-progress {}'.format(Jobs.dumps(jobs)))
    return web.json_response(jobs, dumps=Jobs.dumps, status=200)


@routes.get('/jobs/{job_id}')  # noqa: E302
async def get_job(request):
    """Get job attribute
    Handler to get job attributes for given job_id
    """
    job_id = request.match_info['job_id']
    job = request.app['all_jobs'].get_job_by_job_id(job_id)

    if job is not None:
        _logger.debug('Job found with job_id : {} '.format(job_id))
        return web.json_response({"job": job.get_dict()}, status=200)
    else:
        _logger.debug('Job missing with job_id : {} '.format(job_id))
        return web.json_response(
            {'ErrorResponse': 'Job Not Found!'}, status=404)


@routes.post('/jobs')  # noqa: E302
async def add_job(request):
    """Add job in the queue
    Handler to add jobs to the queue
    """
    job_record = await request.json()
    job = request.app['all_jobs'].add_job_using_json(job_record)
    if job is not None:
        # Start the async replication
        _logger.debug('Starting Replication Job : {} '.format(
            json.dumps(job, cls=JobJsonEncoder)))
        asyncio.create_task(
            TransferInitiator.start(
                job, request.app))

        _logger.info('Started Replication Job with job_id : {} '.format(
            job.get_job_id()))
        _logger.debug('Started Replication Job : {} '.format(
            json.dumps(job, cls=JobJsonEncoder)))

        return web.json_response({'job': job.get_dict()}, status=201)
    else:
        # Job is already posted and its duplicate. Discard the duplicate.
        msg = 'Replication Job already exists! Replication id : {} '.\
            format(job_record[ReplicationJobRecordKey.ID])
        _logger.debug(msg)

        return web.json_response({'ErrorResponse': msg}, status=409)


@routes.delete('/jobs/{job_id}')  # noqa: E302
async def abort_job(request):
    """Abort a job
    Handler to abort a job with given job_id
    """
    job_id = request.match_info['job_id']
    _logger.debug('Aborting Job with job_id {}'.format(job_id))
    # XXX Perform real abort...
    job = request.app['all_jobs'].remove_job_by_job_id(job_id)
    if job is not None:
        # Perform the abort
        job.abort()
        _logger.debug('Aborted Job with job_id {}'.format(job_id))
        return web.json_response({'job_id': job_id}, status=204)
    else:
        _logger.debug('Missing Job with job_id {}'.format(job_id))
        return web.json_response(
            {'ErrorResponse': 'Job Not Found!'}, status=404)