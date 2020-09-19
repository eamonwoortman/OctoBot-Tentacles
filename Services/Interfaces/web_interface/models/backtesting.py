#  Drakkar-Software OctoBot-Interfaces
#  Copyright (c) Drakkar-Software, All rights reserved.
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3.0 of the License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library.
from os import remove
from asyncio import gather
from datetime import datetime

from octobot.api.backtesting import create_independent_backtesting, \
    initialize_and_run_independent_backtesting, \
    get_independent_backtesting_progress, is_independent_backtesting_in_progress, \
    get_independent_backtesting_report, is_independent_backtesting_finished, stop_independent_backtesting, \
    is_independent_backtesting_stopped
from octobot.api.strategy_optimizer import is_optimizer_in_progress
from octobot_commons.logging.logging_util import get_logger
from octobot_backtesting.api.data_file_converters import convert_data_file
from octobot_backtesting.api.exchange_data_collector import collect_exchange_historical_data
from octobot_backtesting.constants import BACKTESTING_FILE_PATH
from octobot_backtesting.api.data_file import get_all_available_data_files, get_file_description, delete_data_file
from octobot_services.interfaces.util.bot import get_global_config, get_bot_api, get_edited_config
from octobot_services.interfaces.util.util import run_in_bot_main_loop, run_in_bot_async_executor
from octobot_tentacles_manager.api.configurator import get_tentacles_setup_config
from tentacles.Services.Interfaces.web_interface.constants import BOT_TOOLS_BACKTESTING, BOT_TOOLS_BACKTESTING_SOURCE, \
    BOT_TOOLS_STRATEGY_OPTIMIZER
from tentacles.Services.Interfaces.web_interface.web_interface import WebInterface
import octobot_commons.config_manager as config_manager

LOGGER = get_logger("DataCollectorWebInterfaceModel")

BACKTESTING_CONFIG_DATE_RANGE = "date_range"
BACKTESTING_CONFIG_DATE_RANGE_START = "start_date"
BACKTESTING_CONFIG_DATE_RANGE_END = "end_date"

async def _get_description(data_file, files_with_description):
    description = await get_file_description(data_file)
    if description is not None:
        files_with_description[data_file] = description


async def _retrieve_data_files_with_description(files):
    files_with_description = {}
    await gather(*[_get_description(data_file, files_with_description) for data_file in files])
    return files_with_description


def get_data_files_with_description():
    files = get_all_available_data_files()
    return run_in_bot_async_executor(_retrieve_data_files_with_description(files))

def update_backtesting_settings(start_date_string, end_date_string):
    current_edited_config = get_edited_config()
    start_date = datetime.fromisoformat(start_date_string)
    end_date = datetime.fromisoformat(end_date_string)

    if (start_date is None or end_date is None):
        return

    if BACKTESTING_CONFIG_DATE_RANGE not in current_edited_config:
        current_edited_config[BACKTESTING_CONFIG_DATE_RANGE] = {BACKTESTING_CONFIG_DATE_RANGE_START: start_date_string, BACKTESTING_CONFIG_DATE_RANGE_END: end_date_string}
    else:
        current_edited_config[BACKTESTING_CONFIG_DATE_RANGE][BACKTESTING_CONFIG_DATE_RANGE_START] = start_date_string
        current_edited_config[BACKTESTING_CONFIG_DATE_RANGE][BACKTESTING_CONFIG_DATE_RANGE_END] = end_date_string
        
    config_manager.simple_save_config_update(current_edited_config)

def start_backtesting_using_specific_files(files, source, reset_tentacle_config=False, run_on_common_part_only=True, range_start_string="", range_end_string=""):
    try:
        tools = WebInterface.tools
        previous_independant_backtesting = tools[BOT_TOOLS_BACKTESTING]
        if tools[BOT_TOOLS_STRATEGY_OPTIMIZER] and is_optimizer_in_progress(tools[BOT_TOOLS_STRATEGY_OPTIMIZER]):
            return False, "Optimizer already running"
        elif previous_independant_backtesting and \
                is_independent_backtesting_in_progress(previous_independant_backtesting):
            return False, "A backtesting is already running"
        else:
            if previous_independant_backtesting:
                run_in_bot_main_loop(stop_independent_backtesting(previous_independant_backtesting))
            if reset_tentacle_config:
                tentacles_setup_config = get_tentacles_setup_config()
            else:
                tentacles_setup_config = get_bot_api().get_edited_tentacles_config()
            update_backtesting_settings(range_start_string, range_end_string)
            config = get_global_config()
            independent_backtesting = create_independent_backtesting(config,
                                                                     tentacles_setup_config,
                                                                     files,
                                                                     run_on_common_part_only=run_on_common_part_only)
            run_in_bot_main_loop(initialize_and_run_independent_backtesting(independent_backtesting), blocking=False)
            tools[BOT_TOOLS_BACKTESTING] = independent_backtesting
            tools[BOT_TOOLS_BACKTESTING_SOURCE] = source
            return True, "Backtesting started"
    except Exception as e:
        LOGGER.exception(e)
        return False, f"Error when starting backtesting: {e}"


def get_backtesting_status():
    if WebInterface.tools[BOT_TOOLS_BACKTESTING] is not None:
        independent_backtesting = WebInterface.tools[BOT_TOOLS_BACKTESTING]
        if is_independent_backtesting_in_progress(independent_backtesting):
            return "computing", get_independent_backtesting_progress(independent_backtesting) * 100
        if is_independent_backtesting_finished(independent_backtesting) or \
                is_independent_backtesting_stopped(independent_backtesting):
            return "finished", 100
        return "starting", 0
    return "not started", 0


def get_backtesting_report(source):
    tools = WebInterface.tools
    if tools[BOT_TOOLS_BACKTESTING]:
        backtesting = tools[BOT_TOOLS_BACKTESTING]
        if tools[BOT_TOOLS_BACKTESTING_SOURCE] == source:
            return run_in_bot_async_executor(get_independent_backtesting_report(backtesting))
    return {}


def get_delete_data_file(file_name):
    deleted, error = delete_data_file(file_name)
    if deleted:
        return deleted, f"{file_name} deleted"
    else:
        return deleted, f"Can't delete {file_name} ({error})"


def collect_data_file(exchange, symbol):
    success = False
    try:
        result = run_in_bot_async_executor(collect_exchange_historical_data(exchange, [symbol]))
        success = True
    except Exception as e:
        result = f"data collector error: {e}"

    if success:
        return success, f"{result} saved"
    else:
        return success, f"Can't collect data for {symbol} on {exchange} ({result})"


async def _convert_into_octobot_data_file_if_necessary(output_file):
    try:
        description = await get_file_description(output_file, data_path="")
        if description is not None:
            # no error: current bot format data
            return f"{output_file} saved"
        else:
            # try to convert into current bot format
            converted_output_file = await convert_data_file(output_file)
            if converted_output_file is not None:
                message = f"Saved into {converted_output_file}"
            else:
                message = "Failed to convert file."
            # remove invalid format file
            remove(output_file)
            return message
    except Exception as e:
        message = f"Error when handling backtesting data file: {e}"
        LOGGER.exception(e, True, message)
        return message


def save_data_file(name, file):
    try:
        output_file = f"{BACKTESTING_FILE_PATH}/{name}"
        file.save(output_file)
        message = run_in_bot_async_executor(_convert_into_octobot_data_file_if_necessary(output_file))
        LOGGER.info(message)
        return True, message
    except Exception as e:
        message = f"Error when saving file: {e}. File can't be saved."
        LOGGER.error(message)
        return False, message
