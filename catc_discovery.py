from shared_utils.catc_restapi_lib import CatcRestApiClient
from shared_utils.log_setup import log_setup
from shared_utils.util import csv_to_dict, dict_to_csv, list_dict_to_csv, print_csv
from catc_config import CATC_IP, CATC_PORT
import logging
import json
import argparse
from argparse import RawTextHelpFormatter
import getpass
import time
import re
import logging


def main():
    log_setup(
        log_level=logging.DEBUG,
        log_file='logs/application_run.log',
        log_term=False,
        max_bytes=50*1024*1024  # 50MB
    )
    logging.info('starting the program.')
    task_info = {}
    discovery_result = {}
    discId_pattern = r'^([0-9]+)$'
    parser = argparse.ArgumentParser(description='Device Discovery.', formatter_class=RawTextHelpFormatter)
    parser.add_argument('--file', dest='file',
                        help='Devices Information in CSV format, using comma as delimiter')
    parser.add_argument('--mode', dest='mode',
                        help='add, delete, assign')
    parser.add_argument('--name', dest='name',
                        help='<Job Name>')
    parser.add_argument('--remove_old_device_with_ip_conflict',
                        dest='remove_old_device_with_ip_conflict',
                        action='store_true',
                        help='Remove old device when discovery finds IP conflict')
    args = parser.parse_args()
    print('='*20)
    username = input('Username: ')
    password = getpass.getpass()
    print('='*20)
    logging.info('logging to CATC.')
    catc = CatcRestApiClient(CATC_IP, CATC_PORT, username, password)
    if args.mode == 'add':
        logging.info('loading CSV data file.')
        duplicated_ip_set = {}
        duplicated_ip_node_list = []
        nodes_list = csv_to_dict(args.file)
        logging.info('finish loading CSV data file.')
        total_task = len(nodes_list)
        fail_task = 0
        success_task = 0
        complete_discovery = 0
        logging.info('adding discovery tasks.')
        for id, node_info in nodes_list.items():
            task_info[id] = {}
            task_info[id]['Name'] = node_info['name']
            task_info[id]['taskId'] = catc.add_discovery_node(node_info)
            task_info[id]['taskResult'] = 'WAITING'
            discovery_result[id] = {}
            discovery_result[id]['Name'] = node_info['name']
            discovery_result[id]['taskResult'] = 'WAITING'
        logging.info('adding discovery tasks done.')
        logging.info('checking status for discovery tasks .')
        while True:
            time.sleep(5)
            for id in nodes_list:
                if 'tStatus' in task_info[id]:
                    if task_info[id]['tStatus'] == 'checked':
                        continue
                else:
                    logging.info(f'getting task info for id: {id}, taskId: {task_info[id]["taskId"]}.')
                    task_info[id]['taskInfo'] = catc.get_task_info(task_info[id]['taskId'])
                    if task_info[id]['taskInfo']['isError'] == True and discovery_result[id]['taskResult'] == 'WAITING':
                        task_info[id]['taskResult'] = 'FAIL'
                        task_info[id]['tStatus'] = 'checked'
                        task_info[id]['failureReason'] = task_info[id]['taskInfo']['failureReason']
                        discovery_result[id]['discId'] = ''
                        discovery_result[id]['taskResult'] = 'FAIL'
                        discovery_result[id]['taskId'] = task_info[id]['taskId']
                        fail_task += 1
                        logging.info(f'task id: {id} is executed, but fail. {task_info[id]["tStatus"]}')
                        logging.info(f'fail task: {fail_task}')
                    else:
                        match = re.search(discId_pattern, task_info[id]['taskInfo']['progress'])
                        if match and discovery_result[id]['taskResult'] == 'WAITING':
                            task_info[id]['taskResult'] = 'SUCCESS'
                            task_info[id]['tStatus'] = 'checked'
                            task_info[id]['failureReason'] = ''
                            discovery_result[id]['discId'] = match.group()
                            discovery_result[id]['taskResult'] = 'SUCCESS'
                            discovery_result[id]['taskId'] = task_info[id]['taskId']
                            success_task += 1
                            logging.info(f'Task id: {id} is executed, and success. {task_info[id]["tStatus"]}')
                            logging.info(f'Successful task: {success_task}')
                        elif match and discovery_result[id]['taskResult'] == 'SUCCESS':
                            continue
                        else:
                            continue
            if total_task == success_task + fail_task:
                logging.info(f'total_task: {total_task}, success_task: {success_task}, fail_task: {fail_task}')
                logging.info(f'total_task({total_task}) = succes_task({success_task}) + fail_task({fail_task})')
                break
        logging.info('all discovery tasks are excecuted.')
        total_discovery = total_task - fail_task
        logging.info(f'total_discovery({total_discovery}) = total_task({total_task}) - fail_task({fail_task})')
        logging.info(f'total_discovery: {total_discovery}')
        logging.debug(f'task_info: {json.dumps(task_info, indent=2)}')
        logging.debug(f'discovery_result: {json.dumps(discovery_result, indent=2)}')
        logging.info('checking discovery status.')
        while True:
            time.sleep(5)
            for id in nodes_list:
                if discovery_result[id]['discId']:
                    if 'dStatus' in discovery_result[id]:
                        if discovery_result[id]['dStatus'] == 'checked':
                            continue
                    else:
                        logging.info(f'getting discovery info for: {id}, discId: {discovery_result[id]["discId"]}')
                        discovery_result[id]['discInfo'] = catc.get_discovery_info(discovery_result[id]['discId'])
                        discStatus = discovery_result[id]['discInfo']['discoveryStatus']
                        discCondition = discovery_result[id]['discInfo']['discoveryCondition']
                        logging.info(f'discovery id: {id}, discStatus={discStatus}, discCondition={discCondition}')
                        if discStatus != 'Inactive' and discCondition != 'Complete':
                            continue
                        elif discStatus == 'Inactive' and discCondition == 'Complete':
                            complete_discovery += 1
                            discovery_result[id]['dStatus'] = 'checked'
                            logging.info(f'discovery id: {id} is complete. {discovery_result[id]["dStatus"]}')
                            logging.info(f'complete discovery: {complete_discovery}')
                        else:
                            continue
                else:
                    continue
            if complete_discovery == total_discovery:
                logging.info(f'complete_discovery: {complete_discovery} = total_discovery: {total_discovery}')
                break
        logging.info('All discoveries are complete.')
        logging.debug(f'task_info: {json.dumps(task_info, indent=2)}')
        logging.debug(f'discovery_result: {json.dumps(discovery_result, indent=2)}')
        logging.info('starting prepare discovery_result for csv file.')

        discovery_result_export = []
        for id in nodes_list:
            if discovery_result[id]['discId']:
                logging.info(f'getting discovery result for id: {id}.')
                discovery_result[id]['discResult'] = catc.get_discovery_result(discovery_result[id]['discId'])
                logging.debug(f'{json.dumps(discovery_result[id], indent=2)}')

                if discovery_result[id]['discResult']:
                    if isinstance(discovery_result[id]['discResult'], dict):
                        disc_items = [discovery_result[id]['discResult']]
                    else:
                        disc_items = discovery_result[id]['discResult']
                else:
                    disc_items = []

                summary_row = {
                    'rowType': 'SUMMARY',
                    'Name': discovery_result[id]['Name'],
                    'discId': discovery_result[id]['discId'],
                    'taskResult': discovery_result[id]['taskResult'],
                    'IpAddress': '',
                    'Status': '',
                    'ping': '',
                    'snmp': '',
                    'cli': '',
                    'http': '',
                    'netconf': '',
                    'invCollection': '',
                    'invReachability': '',
                    'deviceHostname': '',
                    'deviceId': '',
                    'errorCode': '',
                    'errorParamCode': '',
                    'errorParams': ''
                }
                discovery_result_export.append(summary_row)

                if disc_items:
                    logging.info(f'Individual discovery results for job {discovery_result[id]["Name"]} (discId={discovery_result[id]["discId"]}):')
                    for device in disc_items:
                        error_code = device.get('errorCode') or device.get('error_code') or ''
                        error_description = device.get('errorDescription') or device.get('error_description') or ''

                        if not error_code or not error_description:
                            nested_errors = device.get('errors') or device.get('errorList') or []
                            if isinstance(nested_errors, list) and nested_errors:
                                first_error = nested_errors[0]
                                if isinstance(first_error, dict):
                                    if not error_code:
                                        error_code = first_error.get('errorCode') or first_error.get('code') or ''
                                    if not error_description:
                                        error_description = first_error.get('errorDescription') or first_error.get('description') or first_error.get('message') or ''

                        if not error_description:
                            error_description = device.get('reachabilityFailureReason') or ''

                        error_param_code = ''
                        error_params = ''
                        if error_description:
                            parsed_error = None
                            if isinstance(error_description, dict):
                                parsed_error = error_description
                            elif isinstance(error_description, str):
                                desc_text = error_description.strip()
                                if desc_text.startswith('{') and desc_text.endswith('}'):
                                    try:
                                        parsed_error = json.loads(desc_text)
                                    except Exception:
                                        parsed_error = None

                            if isinstance(parsed_error, dict):
                                i18n_data = parsed_error.get('i18n')
                                if isinstance(i18n_data, dict):
                                    error_param_code = i18n_data.get('code', '') or error_param_code
                                    i18n_params = i18n_data.get('params', [])
                                    if isinstance(i18n_params, list):
                                        error_params = '; '.join([str(item) for item in i18n_params if item is not None])
                                    elif i18n_params is not None:
                                        error_params = str(i18n_params)

                                if not error_param_code:
                                    error_param_code = parsed_error.get('code', '')
                                if not error_params:
                                    root_params = parsed_error.get('params', [])
                                    if isinstance(root_params, list):
                                        error_params = '; '.join([str(item) for item in root_params if item is not None])
                                    elif root_params is not None:
                                        error_params = str(root_params)

                            if not error_param_code:
                                code_match = re.search(r'(?i)\b(?:error\s*code|code|param\s*code)\s*[:=]\s*([A-Za-z0-9_.-]+)', str(error_description))
                                if code_match:
                                    error_param_code = code_match.group(1)

                            if not error_params:
                                params_match = re.search(r'(?i)\b(?:params?|parameters?)\s*[:=]\s*(.+)$', str(error_description))
                                if params_match:
                                    error_params = params_match.group(1).strip()

                            if not error_params:
                                bracket_match = re.search(r'(\[[^\]]*\]|\{[^\}]*\})', str(error_description))
                                if bracket_match:
                                    error_params = bracket_match.group(1)

                        if not error_param_code:
                            error_param_code = error_code

                        logging.info(f'  hostname={device.get("hostname", "N/A")}, ip={device.get("managementIpAddress", "N/A")}, reachability={device.get("reachabilityStatus", "N/A")}, errorCode={error_code or "N/A"}, errorParamCode={error_param_code or "N/A"}, errorParams={error_params or "N/A"}')

                        detail_row = {
                            'rowType': 'DETAIL',
                            'Name': discovery_result[id]['Name'],
                            'discId': discovery_result[id]['discId'],
                            'taskResult': '',
                            'IpAddress': device.get('managementIpAddress', ''),
                            'Status': device.get('reachabilityStatus', '').upper(),
                            'ping': device.get('pingStatus', ''),
                            'snmp': device.get('snmpStatus', ''),
                            'cli': device.get('cliStatus', ''),
                            'http': device.get('httpStatus', ''),
                            'netconf': device.get('netconfStatus', ''),
                            'invCollection': device.get('inventoryCollectionStatus', ''),
                            'invReachability': device.get('inventoryReachabilityStatus', ''),
                            'deviceHostname': device.get('hostname', ''),
                            'deviceId': device.get('id', ''),
                            'errorCode': error_code,
                            'errorParamCode': error_param_code,
                            'errorParams': error_params
                        }
                        discovery_result_export.append(detail_row)

                        if args.remove_old_device_with_ip_conflict:
                            error_code_upper = (error_code or '').upper()
                            error_param_code_upper = (error_param_code or '').upper()
                            error_params_upper = (error_params or '').upper()
                            has_conflict_keyword = 'CONFLICT' in error_code_upper or 'CONFLICT' in error_param_code_upper or 'CONFLICT' in error_params_upper
                            has_ip_keyword = 'IP' in error_code_upper or 'IP ADDRESS' in error_params_upper or 'IP ADDRESS' in error_code_upper
                            is_ip_conflict_error = has_conflict_keyword and has_ip_keyword

                            conflict_ip = device.get('managementIpAddress', '')
                            conflict_device_id = device.get('id', '')
                            if is_ip_conflict_error and conflict_ip and conflict_ip not in duplicated_ip_set:
                                duplicated_ip_set[conflict_ip] = conflict_device_id
                                duplicated_node = dict(nodes_list[id])
                                duplicated_node['discoveryType'] = 'SINGLE'
                                duplicated_node['ipAddressList'] = conflict_ip
                                duplicated_node['name'] = f'{conflict_ip}_rediscovery'
                                duplicated_ip_node_list.append(duplicated_node)
                                logging.info(f'Added rediscovery node for IP conflict: {conflict_ip}, existingDeviceId={conflict_device_id or "N/A"}')
            else:
                summary_row = {
                    'rowType': 'SUMMARY',
                    'Name': discovery_result[id]['Name'],
                    'discId': '',
                    'taskResult': discovery_result[id]['taskResult'],
                    'IpAddress': '',
                    'Status': '',
                    'ping': '',
                    'snmp': '',
                    'cli': '',
                    'http': '',
                    'netconf': '',
                    'invCollection': '',
                    'invReachability': '',
                    'deviceHostname': '',
                    'deviceId': '',
                    'errorCode': '',
                    'errorParamCode': '',
                    'errorParams': ''
                }
                discovery_result_export.append(summary_row)

        logging.info('complete prepare discovery_result for csv file.')
        logging.debug(f'discovery_result_export: {json.dumps(discovery_result_export, indent=2)}')
        logging.info('saving task_result.csv.')
        dict_to_csv(task_info,
                    'task_result.csv',
                    'Name',
                    'taskId',
                    'taskResult',
                    'failureReason')
        logging.info('saving discovery_result.csv.')
        list_dict_to_csv(discovery_result_export,
                         'discovery_result.csv',
                         'rowType',
                         'Name',
                         'discId',
                         'taskResult',
                         'IpAddress',
                         'Status',
                         'ping',
                         'snmp',
                         'cli',
                         'http',
                         'netconf',
                         'invCollection',
                         'invReachability',
                         'deviceHostname',
                         'deviceId',
                         'errorCode',
                         'errorParamCode',
                         'errorParams')
        print_csv('task_result.csv', 165)
        print_csv(
            'discovery_result.csv',
            260,
            exclude_columns=['invCollection', 'invReachability', 'deviceHostname', 'deviceId', 'errorParams']
        )

        if args.remove_old_device_with_ip_conflict:
            logging.info('duplicated_ip_set: %s', json.dumps(duplicated_ip_set, indent=2))
            logging.debug('duplicated_ip_node_list: %s', json.dumps(duplicated_ip_node_list, indent=2))
            if duplicated_ip_set:
                logging.info('Deleting old devices with IP conflict.')
                print('\n' + '='*60)
                print('DELETING OLD DEVICES WITH IP CONFLICT')
                print('='*60)
                for conflict_ip, device_id in duplicated_ip_set.items():
                    if not device_id:
                        logging.warning(f'Skipping device delete for conflict IP {conflict_ip}: missing device ID')
                        print(f'[SKIP] IP {conflict_ip}: Missing device ID')
                        continue

                    logging.info(f'Starting delete for conflict IP {conflict_ip}, device ID {device_id}')
                    print(f'\n[DELETE START] IP: {conflict_ip}, Device ID: {device_id}')
                    delete_task_id = catc.delete_device_by_id(device_id)

                    if not delete_task_id:
                        logging.warning(f'Device delete did not return task ID for conflict IP {conflict_ip}, device ID {device_id}')
                        print(f'[ERROR] IP {conflict_ip}: No task ID returned from delete request')
                        continue

                    print(f'[DELETE TASK] IP: {conflict_ip}, Task ID: {delete_task_id}')
                    max_attempts = 60
                    attempt = 0
                    while attempt < max_attempts:
                        attempt += 1
                        time.sleep(5)
                        delete_task_info = catc.get_task_info(delete_task_id)

                        if not delete_task_info:
                            logging.warning(f'Could not retrieve delete task status for task ID {delete_task_id} (attempt {attempt}/{max_attempts})')
                            print(f'[WARNING] IP {conflict_ip}: Could not retrieve task status (attempt {attempt}/{max_attempts})')
                            continue

                        is_error = delete_task_info.get('isError', False)
                        end_time = delete_task_info.get('endTime')
                        progress = delete_task_info.get('progress', '')
                        failure_reason = delete_task_info.get('failureReason', '')

                        if is_error:
                            error_msg = failure_reason or progress or "Unknown error"
                            logging.error(f'Device delete failed for conflict IP {conflict_ip}, device ID {device_id}, task ID {delete_task_id}, failureReason={error_msg}')
                            print(f'[DELETE FAILED] IP: {conflict_ip}, Reason: {error_msg}')
                            break

                        if end_time:
                            logging.info(f'Device delete completed for conflict IP {conflict_ip}, device ID {device_id}, task ID {delete_task_id}, progress={progress}')
                            print(f'[DELETE SUCCESS] IP: {conflict_ip}, Progress: {progress}')
                            break

                        logging.debug(f'Device delete still in progress for conflict IP {conflict_ip}, task ID {delete_task_id} (attempt {attempt}/{max_attempts})')
                        print(f'[DELETE IN PROGRESS] IP: {conflict_ip} (attempt {attempt}/{max_attempts})', end='\r')
                    else:
                        logging.warning(f'Device delete timed out for conflict IP {conflict_ip}, device ID {device_id}, task ID {delete_task_id}')
                        print(f'[DELETE TIMEOUT] IP: {conflict_ip}: Exceeded maximum attempts')
                print('='*60 + '\n')

                if duplicated_ip_node_list:
                    logging.info('Starting rediscovery for duplicated IP nodes.')
                    rediscovery_nodes = {
                        index: node_info for index, node_info in enumerate(duplicated_ip_node_list, start=1)
                    }
                    rediscovery_task_info = {}
                    rediscovery_result = {}
                    rediscovery_result_export = []
                    rediscovery_total_task = len(rediscovery_nodes)
                    rediscovery_fail_task = 0
                    rediscovery_success_task = 0
                    rediscovery_complete_discovery = 0

                    logging.info('adding rediscovery tasks.')
                    for id, node_info in rediscovery_nodes.items():
                        rediscovery_task_info[id] = {}
                        rediscovery_task_info[id]['Name'] = node_info['name']
                        rediscovery_task_info[id]['taskId'] = catc.add_discovery_node(node_info)
                        rediscovery_task_info[id]['taskResult'] = 'WAITING'
                        rediscovery_result[id] = {}
                        rediscovery_result[id]['Name'] = node_info['name']
                        rediscovery_result[id]['taskResult'] = 'WAITING'
                    logging.info('adding rediscovery tasks done.')

                    logging.info('checking status for rediscovery tasks.')
                    while True:
                        time.sleep(5)
                        for id in rediscovery_nodes:
                            if 'tStatus' in rediscovery_task_info[id]:
                                if rediscovery_task_info[id]['tStatus'] == 'checked':
                                    continue
                            else:
                                logging.info(f'getting rediscovery task info for id: {id}, taskId: {rediscovery_task_info[id]["taskId"]}.')
                                rediscovery_task_info[id]['taskInfo'] = catc.get_task_info(rediscovery_task_info[id]['taskId'])
                                if rediscovery_task_info[id]['taskInfo']['isError'] == True and rediscovery_result[id]['taskResult'] == 'WAITING':
                                    rediscovery_task_info[id]['taskResult'] = 'FAIL'
                                    rediscovery_task_info[id]['tStatus'] = 'checked'
                                    rediscovery_task_info[id]['failureReason'] = rediscovery_task_info[id]['taskInfo']['failureReason']
                                    rediscovery_result[id]['discId'] = ''
                                    rediscovery_result[id]['taskResult'] = 'FAIL'
                                    rediscovery_result[id]['taskId'] = rediscovery_task_info[id]['taskId']
                                    rediscovery_fail_task += 1
                                    logging.info(f'rediscovery task id: {id} is executed, but fail. {rediscovery_task_info[id]["tStatus"]}')
                                    logging.info(f'rediscovery fail task: {rediscovery_fail_task}')
                                else:
                                    match = re.search(discId_pattern, rediscovery_task_info[id]['taskInfo']['progress'])
                                    if match and rediscovery_result[id]['taskResult'] == 'WAITING':
                                        rediscovery_task_info[id]['taskResult'] = 'SUCCESS'
                                        rediscovery_task_info[id]['tStatus'] = 'checked'
                                        rediscovery_task_info[id]['failureReason'] = ''
                                        rediscovery_result[id]['discId'] = match.group()
                                        rediscovery_result[id]['taskResult'] = 'SUCCESS'
                                        rediscovery_result[id]['taskId'] = rediscovery_task_info[id]['taskId']
                                        rediscovery_success_task += 1
                                        logging.info(f'Rediscovery task id: {id} is executed, and success. {rediscovery_task_info[id]["tStatus"]}')
                                        logging.info(f'Successful rediscovery task: {rediscovery_success_task}')
                                    elif match and rediscovery_result[id]['taskResult'] == 'SUCCESS':
                                        continue
                                    else:
                                        continue
                        if rediscovery_total_task == rediscovery_success_task + rediscovery_fail_task:
                            logging.info(f'rediscovery total_task: {rediscovery_total_task}, success_task: {rediscovery_success_task}, fail_task: {rediscovery_fail_task}')
                            logging.info(f'rediscovery total_task({rediscovery_total_task}) = succes_task({rediscovery_success_task}) + fail_task({rediscovery_fail_task})')
                            break

                    logging.info('all rediscovery tasks are executed.')
                    rediscovery_total_discovery = rediscovery_total_task - rediscovery_fail_task
                    logging.info(f'rediscovery total_discovery({rediscovery_total_discovery}) = total_task({rediscovery_total_task}) - fail_task({rediscovery_fail_task})')
                    logging.info(f'rediscovery total_discovery: {rediscovery_total_discovery}')
                    logging.debug(f'rediscovery_task_info: {json.dumps(rediscovery_task_info, indent=2)}')
                    logging.debug(f'rediscovery_result: {json.dumps(rediscovery_result, indent=2)}')

                    logging.info('checking rediscovery status.')
                    while True:
                        time.sleep(5)
                        for id in rediscovery_nodes:
                            if rediscovery_result[id]['discId']:
                                if 'dStatus' in rediscovery_result[id]:
                                    if rediscovery_result[id]['dStatus'] == 'checked':
                                        continue
                                else:
                                    logging.info(f'getting rediscovery info for: {id}, discId: {rediscovery_result[id]["discId"]}')
                                    rediscovery_result[id]['discInfo'] = catc.get_discovery_info(rediscovery_result[id]['discId'])
                                    discStatus = rediscovery_result[id]['discInfo']['discoveryStatus']
                                    discCondition = rediscovery_result[id]['discInfo']['discoveryCondition']
                                    logging.info(f'rediscovery id: {id}, discStatus={discStatus}, discCondition={discCondition}')
                                    if discStatus != 'Inactive' and discCondition != 'Complete':
                                        continue
                                    elif discStatus == 'Inactive' and discCondition == 'Complete':
                                        rediscovery_complete_discovery += 1
                                        rediscovery_result[id]['dStatus'] = 'checked'
                                        logging.info(f'rediscovery id: {id} is complete. {rediscovery_result[id]["dStatus"]}')
                                        logging.info(f'complete rediscovery: {rediscovery_complete_discovery}')
                                    else:
                                        continue
                            else:
                                continue
                        if rediscovery_complete_discovery == rediscovery_total_discovery:
                            logging.info(f'rediscovery complete_discovery: {rediscovery_complete_discovery} = total_discovery: {rediscovery_total_discovery}')
                            break

                    logging.info('All rediscoveries are complete.')
                    logging.debug(f'rediscovery_task_info: {json.dumps(rediscovery_task_info, indent=2)}')
                    logging.debug(f'rediscovery_result: {json.dumps(rediscovery_result, indent=2)}')
                    logging.info('starting prepare rediscovery_result for csv file.')

                    for id in rediscovery_nodes:
                        if rediscovery_result[id]['discId']:
                            logging.info(f'getting rediscovery result for id: {id}.')
                            rediscovery_result[id]['discResult'] = catc.get_discovery_result(rediscovery_result[id]['discId'])
                            logging.debug(f'{json.dumps(rediscovery_result[id], indent=2)}')

                            if rediscovery_result[id]['discResult']:
                                if isinstance(rediscovery_result[id]['discResult'], dict):
                                    disc_items = [rediscovery_result[id]['discResult']]
                                else:
                                    disc_items = rediscovery_result[id]['discResult']
                            else:
                                disc_items = []

                            summary_row = {
                                'rowType': 'SUMMARY',
                                'Name': rediscovery_result[id]['Name'],
                                'discId': rediscovery_result[id]['discId'],
                                'taskResult': rediscovery_result[id]['taskResult'],
                                'IpAddress': '',
                                'Status': '',
                                'ping': '',
                                'snmp': '',
                                'cli': '',
                                'http': '',
                                'netconf': '',
                                'invCollection': '',
                                'invReachability': '',
                                'deviceHostname': '',
                                'deviceId': '',
                                'errorCode': '',
                                'errorParamCode': '',
                                'errorParams': ''
                            }
                            rediscovery_result_export.append(summary_row)

                            if disc_items:
                                logging.info(f'Individual rediscovery results for job {rediscovery_result[id]["Name"]} (discId={rediscovery_result[id]["discId"]}):')
                                for device in disc_items:
                                    error_code = device.get('errorCode') or device.get('error_code') or ''
                                    error_description = device.get('errorDescription') or device.get('error_description') or ''

                                    if not error_code or not error_description:
                                        nested_errors = device.get('errors') or device.get('errorList') or []
                                        if isinstance(nested_errors, list) and nested_errors:
                                            first_error = nested_errors[0]
                                            if isinstance(first_error, dict):
                                                if not error_code:
                                                    error_code = first_error.get('errorCode') or first_error.get('code') or ''
                                                if not error_description:
                                                    error_description = first_error.get('errorDescription') or first_error.get('description') or first_error.get('message') or ''

                                    if not error_description:
                                        error_description = device.get('reachabilityFailureReason') or ''

                                    error_param_code = ''
                                    error_params = ''
                                    if error_description:
                                        parsed_error = None
                                        if isinstance(error_description, dict):
                                            parsed_error = error_description
                                        elif isinstance(error_description, str):
                                            desc_text = error_description.strip()
                                            if desc_text.startswith('{') and desc_text.endswith('}'):
                                                try:
                                                    parsed_error = json.loads(desc_text)
                                                except Exception:
                                                    parsed_error = None

                                        if isinstance(parsed_error, dict):
                                            i18n_data = parsed_error.get('i18n')
                                            if isinstance(i18n_data, dict):
                                                error_param_code = i18n_data.get('code', '') or error_param_code
                                                i18n_params = i18n_data.get('params', [])
                                                if isinstance(i18n_params, list):
                                                    error_params = '; '.join([str(item) for item in i18n_params if item is not None])
                                                elif i18n_params is not None:
                                                    error_params = str(i18n_params)

                                            if not error_param_code:
                                                error_param_code = parsed_error.get('code', '')
                                            if not error_params:
                                                root_params = parsed_error.get('params', [])
                                                if isinstance(root_params, list):
                                                    error_params = '; '.join([str(item) for item in root_params if item is not None])
                                                elif root_params is not None:
                                                    error_params = str(root_params)

                                        if not error_param_code:
                                            code_match = re.search(r'(?i)\b(?:error\s*code|code|param\s*code)\s*[:=]\s*([A-Za-z0-9_.-]+)', str(error_description))
                                            if code_match:
                                                error_param_code = code_match.group(1)

                                        if not error_params:
                                            params_match = re.search(r'(?i)\b(?:params?|parameters?)\s*[:=]\s*(.+)$', str(error_description))
                                            if params_match:
                                                error_params = params_match.group(1).strip()

                                        if not error_params:
                                            bracket_match = re.search(r'(\[[^\]]*\]|\{[^\}]*\})', str(error_description))
                                            if bracket_match:
                                                error_params = bracket_match.group(1)

                                    if not error_param_code:
                                        error_param_code = error_code

                                    logging.info(f'  hostname={device.get("hostname", "N/A")}, ip={device.get("managementIpAddress", "N/A")}, reachability={device.get("reachabilityStatus", "N/A")}, errorCode={error_code or "N/A"}, errorParamCode={error_param_code or "N/A"}, errorParams={error_params or "N/A"}')

                                    detail_row = {
                                        'rowType': 'DETAIL',
                                        'Name': rediscovery_result[id]['Name'],
                                        'discId': rediscovery_result[id]['discId'],
                                        'taskResult': '',
                                        'IpAddress': device.get('managementIpAddress', ''),
                                        'Status': device.get('reachabilityStatus', '').upper(),
                                        'ping': device.get('pingStatus', ''),
                                        'snmp': device.get('snmpStatus', ''),
                                        'cli': device.get('cliStatus', ''),
                                        'http': device.get('httpStatus', ''),
                                        'netconf': device.get('netconfStatus', ''),
                                        'invCollection': device.get('inventoryCollectionStatus', ''),
                                        'invReachability': device.get('inventoryReachabilityStatus', ''),
                                        'deviceHostname': device.get('hostname', ''),
                                        'deviceId': device.get('id', ''),
                                        'errorCode': error_code,
                                        'errorParamCode': error_param_code,
                                        'errorParams': error_params
                                    }
                                    rediscovery_result_export.append(detail_row)
                        else:
                            summary_row = {
                                'rowType': 'SUMMARY',
                                'Name': rediscovery_result[id]['Name'],
                                'discId': '',
                                'taskResult': rediscovery_result[id]['taskResult'],
                                'IpAddress': '',
                                'Status': '',
                                'ping': '',
                                'snmp': '',
                                'cli': '',
                                'http': '',
                                'netconf': '',
                                'invCollection': '',
                                'invReachability': '',
                                'deviceHostname': '',
                                'deviceId': '',
                                'errorCode': '',
                                'errorParamCode': '',
                                'errorParams': ''
                            }
                            rediscovery_result_export.append(summary_row)

                    logging.info('complete prepare rediscovery_result for csv file.')
                    logging.debug(f'rediscovery_result_export: {json.dumps(rediscovery_result_export, indent=2)}')
                    logging.info('saving task_result_rediscovery.csv.')
                    dict_to_csv(rediscovery_task_info,
                                'task_result_rediscovery.csv',
                                'Name',
                                'taskId',
                                'taskResult',
                                'failureReason')
                    logging.info('saving discovery_result_rediscovery.csv.')
                    list_dict_to_csv(rediscovery_result_export,
                                    'discovery_result_rediscovery.csv',
                                    'rowType',
                                    'Name',
                                    'discId',
                                    'taskResult',
                                    'IpAddress',
                                    'Status',
                                    'ping',
                                    'snmp',
                                    'cli',
                                    'http',
                                    'netconf',
                                    'invCollection',
                                    'invReachability',
                                    'deviceHostname',
                                    'deviceId',
                                    'errorCode',
                                    'errorParamCode',
                                    'errorParams')
                    print_csv('task_result_rediscovery.csv', 165)
                    print_csv(
                        'discovery_result_rediscovery.csv',
                        260,
                        exclude_columns=['invCollection', 'invReachability', 'deviceHostname', 'deviceId', 'errorParams']
                    )

        logging.info('logging out from CATC.')
        catc.logout()
            
    elif args.mode == 'delete':
        logging.info('Deleting all discovery tasks.')
        catc.delete_alldiscovery()
        logging.info('logging out from CATC.')
        catc.logout()
    elif args.mode == 'assign':
        nodes_list = csv_to_dict(args.file)
        for item in nodes_list:
            site_id = catc.get_siteid_by_name(nodes_list[item]['site'])
            device_ip = nodes_list[item]['ip']
            nodes_list[item]['executionStatus'], nodes_list[item]['executionError'] = catc.assign_device_to_site(site_id, device_ip)
        print(json.dumps(nodes_list, indent=2))
        logging.info('saving assign_site_result.csv.')
        dict_to_csv(nodes_list,
                    'assign_site_result.csv',
                    'ip',
                    'site',
                    'executionStatus',
                    'executionError')
        logging.info('logging out from CATC.')
        catc.logout()


if __name__ == '__main__':
    main()
