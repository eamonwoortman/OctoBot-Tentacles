
/*
 * Drakkar-Software OctoBot
 * Copyright (c) Drakkar-Software, All rights reserved.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 3.0 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library.
 */


function get_selected_files(){
    const selected_modules = [];
    dataFilesTable.rows(
        function ( idx, data, node ) {
            return $(node).find("input[type='checkbox']:checked").length > 0;
        }
    ).eq(0).each(function( index ) {
        selected_modules.push(dataFilesTable.row( index ).data()[1]);
    });
    return selected_modules;
}

function get_selected_date(){
    const data = dataFilesTable.row(function ( idx, data, node ) {
        return $(node).find("input[type='checkbox']:checked").length > 0;
    }).data();
    return data;
}

function getDateRangeFromFields() {
    const startDate = getRangeStartDate();
    const endDate = getRangeEndDate();
    return "range_start="+startDate.toISOString()+"&range_end="+endDate.toISOString();
}

function handle_backtesting_buttons(){
    $("#startBacktesting").click(function(){
        $("#backtesting_progress_bar").show();
        lock_interface();
        const request = get_selected_files();
        const update_url = $("#startBacktesting").attr("start-url");
        const run_on_common_part_only = syncDataOnlyCheckbox.is(":checked");
        const date_range = getDateRangeFromFields();
        start_backtesting(request, `${update_url}&run_on_common_part_only=${run_on_common_part_only}&${date_range}`);
    });
}
function getFormattedDate(date) { 
    var year = date.getFullYear();
  
    var month = (1 + date.getMonth()).toString();
    month = month.length > 1 ? month : '0' + month;
  
    var day = date.getDate().toString();
    day = day.length > 1 ? day : '0' + day;
    return day + '-' + month + '-' + year;
  }
  
function handle_file_selection(){
    const selectable_datafile = $(".selectable_datafile");
    selectable_datafile.unbind('click');
    selectable_datafile.click(function () {
        const row_element = $(this);
        if (row_element.hasClass(selected_item_class)){
            row_element.removeClass(selected_item_class);
            row_element.find(".dataFileCheckbox").prop('checked', false);
        }else{
            row_element.toggleClass(selected_item_class);
            const checkbox = row_element.find(".dataFileCheckbox");
            const symbols = checkbox.attr("symbols");
            const data_file = checkbox.attr("data-file");
            checkbox.prop('checked', true);
            // uncheck same symbols from other rows if any
            $("#dataFilesTable").find("input[type='checkbox']:checked").each(function(){
                if($(this).attr("symbols") === symbols && !($(this).attr("data-file") === data_file)){
                    $(this).closest('tr').removeClass(selected_item_class);
                    $(this).prop('checked', false);
                }
            });
        }
        if($("#dataFilesTable").find("input[type='checkbox']:checked").length > 1){
           syncDataOnlyDiv.removeClass(hidden_class);
        }else{
            syncDataOnlyDiv.addClass(hidden_class);
        }
        lock_interface(false);

        handle_date_range_picker();
    });
}

function reset_date_pickers(){
    $('.input-daterange').each(function(index){
        $(this).datepicker('remove');
     });
}

const isToday = (inputDate) => {
    const today = new Date()
    return inputDate.getDate() == today.getDate() &&
      inputDate.getMonth() == today.getMonth() &&
      inputDate.getFullYear() == today.getFullYear()
}

const clamp = (num, min, max) => {
    return num <= min ? min : num >= max ? max : num;
}

const clampDate = (inputDate, minDate, maxDate) => {
    if (minDate === undefined || maxDate === undefined) {
        return inputDate;
    }
    if (inputDate > maxDate) {
        return maxDate;
    } else if (inputDate < minDate) {
        return minDate;
    } else {
        return inputDate;
    }
}

function getFieldDate(dateField) {
    return dateField.datepicker('getUTCDate');
}
function getRangeStartDate() {
    return getFieldDate($('#daterange-start'));
}
function getRangeEndDate() {
    return getFieldDate($('#daterange-end'));
}


function clamp_date_ranges(min_date, max_date){
    if (min_date === undefined || max_date === undefined) {
        return;
    }
    var endDateField = $('#daterange-end');
    var endDate = max_date;
    if (endDateField.val() !== "") {
        endDate = clampDate(endDateField.datepicker('getUTCDate'), min_date, max_date);
    }
    endDateField.datepicker('setUTCDate', endDate);
    //endDateField.datepicker('update', endDate);
    
    var startDateField = $('#daterange-start');
    var startDate = min_date;
    if (startDateField.val() !== "") {
        startDate = clampDate(startDateField.datepicker('getUTCDate'), min_date, max_date);
    }
    startDateField.datepicker('setUTCDate', startDate);
    //startDateField.datepicker('update', startDate);
}

function handle_date_range_picker(){
    min_date=undefined;
    max_date=undefined;
    const selected_file_date = get_selected_date();
    if (selected_file_date) {
        max_date = new Date(1000 * selected_file_date[6]);
        min_date = new Date(max_date);
        min_date.setDate(min_date.getDate() - 200);
        $('#daterange-start,#daterange-end').prop('disabled', false);
    } else {
        $('#daterange-start,#daterange-end').val('').prop('disabled', true);
    }

    reset_date_pickers();
    clamp_date_ranges(min_date, max_date);

    var dateRangeInputs = $('.input-daterange');
    var datePicker = dateRangeInputs.datepicker({
        format: 'dd-mm-yyyy',
        autoclose: true,
        disableTouchKeyboard: true,
        todayHighlight: false
    });
   
    $('#daterange-start,#daterange-end').datepicker('setStartDate', min_date);
    $('#daterange-start,#daterange-end').datepicker('setEndDate', max_date);

    datePicker.on('changeDate', function(ev) {
        clamp_date_ranges(min_date, max_date);
    });
    
}

const dataFilesTable = $('#dataFilesTable').DataTable({"order": []});
const syncDataOnlyDiv = $("#synchronized-data-only-div");
const syncDataOnlyCheckbox = $("#synchronized-data-only-checkbox");

$(document).ready(function() {
    lock_interface_callbacks.push(function () {
        return get_selected_files() <= 0;
    });
    handle_backtesting_buttons();
    handle_file_selection();
    $('#dataFilesTable').on("draw.dt", function(){
        handle_file_selection();
    });
    lock_interface();

    init_backtesting_status_websocket();
    
    handle_date_range_picker();
    
});
