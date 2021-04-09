/**
 * The entry point
 */

import 'regenerator-runtime/runtime'
import App from './components/app'
import $ from 'jquery'
var csv = require('jquery-csv/src/jquery.csv')


var csvData = [];
var csvHeaders = [];
const api_url = "https://ionutgoesforawalk.xyz:8001";

function updateCsvView(file) {
  $("#csvStatus").html(`Fișierul ales: ${file.name}`);
  var reader = new FileReader();
  reader.onload = function (event) {
    var objects = csv.toObjects(event.target.result);
    csvData = objects;
    if (objects.length == 0) {
      // TODO handle
      return;
    }
    // TODO cleanup
    var headers = Object.keys(objects[0]);
    csvHeaders = headers;
    var html = "<table>" + `<tr>${sum_map(headers, h => `<th>${h}</th>`)}</tr>`
      + sum_map(objects, obj => `<tr>${sum_map(headers, h => `<td>${obj[h]}</td>`)}</tr>`)
      + "</table>";
    $('#csvView').html(html);
    // TODO make sure header can be id
    $('#numberChooser').html(
      sum_map(headers, h => `<option value="${h}">${h}</option>`)
    );
    $('#csvFileInput').val('');
    resetPreviewAndSend();
  };
  reader.readAsText(file);
}

function resetPreviewAndSend() {
  $('#messageCountView').html('');
  $('#messagePreviews').html('');
  $('#statusMessage').html('');
  $('messagesReport').html('');
  disableSending();
}

function disableSending() {
  $('#sendMessagesButton').attr('disabled', true);
  $('#canNotSendExplanation').html("Mesajele trebuie mai înâi previzualizate pentru a putea fi trimise");
}

function enableSending() {
  $('#sendMessagesButton').attr('disabled', false);
  $('#canNotSendExplanation').html("");
}

function setCsvViewNoData() {
  $('#csvView').html("<p class=\"weak-text\">Aici va apărea conținutul fișierului csv</p>");
}

function formatMessage(template, entry, headers) {
  //TODO optimizeable
  headers.forEach(header => {
    var reg = new RegExp(`\\{\\w*${header}\\w*\\}`, "g");
    template = template.replace(reg, entry[header]);
  });
  return template;
}

function generateMessages() {
  console.log("Generating Messages");
  var template = $('#messageText').val();
  var numberHeader = $('#numberChooser').val();
  console.log(template, numberHeader);

  return csvData.map(entry => {
    return {
      'to': entry[numberHeader],
      'message': formatMessage(template, entry, csvHeaders)
    };
  });
}

function updatePreview() {
  var messages = generateMessages();
  $('#messageCountView').html(`Număr mesaje: <b>${messages.length}</b>`)
  $('#messagePreviews').html(sum_map(messages, message => `<li>Către: ${message.to}<br>${message.message}</li>`))
  enableSending();
}

function sum_map(arr, fn) {
  return arr.map(fn).reduce((acc, v) => acc + v, "");
}

function sendRequest() {
  var messages = generateMessages();
  startTransaction()
  $.ajax(`${api_url}/sms_request`, {
    data: JSON.stringify({ messages: generateMessages() }),
    dataType: "json",
    contentType: "application/json; charset=utf-8",
    method: "POST",
    success: result => { console.log("Success!"); startPolling(result.id); },
    error: () => { console.log("error"); }
  });
}


const poll = async (fn, validate, interval) => {
  let attempts = 0;

  const executePoll = async (resolve, reject) => {
    const result = await fn();
    attempts++;

    if (validate(result)) {
      return resolve(result);
      // } else if (maxAttempts && attempts === maxAttempts) {
      //   return reject(new Error('Exceeded max attempts'));
    } else {
      setTimeout(executePoll, interval, resolve, reject);
    }
  };

  return new Promise(executePoll);
};

function startTransaction() {
  $('#statusMessage').html("Se trimite...");
}

function startPolling(request_id) {
  poll(async () => { return await getSMSRequestStatus(request_id); }, statusWrapper => statusWrapper.status != "Received", 1000).then(handleStatus);
}

function handleStatus(statusResponse) {
  $('#statusMessage').html(getMessage(statusResponse));
    var rep = "<tr><th>Trimis?</th><th>Destinatar</th><th>Conținut</th><th>Detalii eșec</th></tr>" +
    sum_map(statusResponse.message_reports, report => `<tr class="${report.sent?"sent":"not-sent"}"><td>${report.sent?"DA":"NU"}</td><td>${report.to}</td>
    <td>${report.message}</td><td>${report.sent?"":report.failure_reason}</td></tr>`)
    console.log(rep);
    $('#messagesReport').html(rep);
}

async function getSMSRequestStatus(requestId) {
  return await $.get(`${api_url}/sms_request/${requestId}/status`);
}

function hacky_post(url) {
  return $.ajax(url, {
    data: JSON.stringify({ pwd: getPwd() }),
    dataType: "json",
    contentType: "application/json; charset=utf-8",
    method: "POST",
  });
}

function getMessage(statusWrapper) {
  switch (statusWrapper.status) {
    case "Success":
      return "Mesajele au fost transmise cu succes!";
    case "Failure":
      return "Au fost probleme la trimiterea mesajelor...";
  }
}

function checkCredit() {
  $('#creditView').html(`Se verifică...`);
  $.get(`${api_url}/credit`).then(creditResponse => $('#creditView').html(`Mesaje rămase: <b>${creditResponse.messages}</b>`));
}

function getAllMessagesReports() {

  $.get(`${api_url}/message_reports`).then(response => {
    var rep = "<tr><th>Data și ora</th><th>Trimis?</th><th>Destinatar</th><th>Conținut</th><th>Detalii eșec</th></tr>" +
    sum_map(response.message_reports, report => `<tr class="${report.sent?"sent":"not-sent"}"><td>${report.datetime}</td><td>${report.sent?"DA":"NU"}</td><td>${report.to}</td>
    <td>${report.message}</td><td>${report.sent?"":report.failure_reason}</td></tr>`)
    console.log(rep);
    $('#oldMessagesReport').html(rep);
  });
}

window.addEventListener('load', () => {
  setCsvViewNoData();
  $('#csvFileInput').on('change', event => updateCsvView(event.target.files[0]));
  $('#loadCsvButton').on('click', () => $('#csvFileInput').trigger('click'));
  $('#createPreviewButton').on('click', updatePreview);
  $('#sendMessagesButton').on('click', sendRequest);
  $('#messageText').on('input', () => resetPreviewAndSend());
  $('#checkCreditButton').on('click', checkCredit);
  $('#getAllMessageReports').on('click', getAllMessagesReports);
})