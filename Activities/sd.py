async function
fillActivityControl(act=-1)
{
// Helper
function
to
add
days
to
a
date
function
addDays(date, days)
{
    let
result = new
Date(date);
result.setDate(result.getDate() + days);
return result;
}

function
sleep(seconds)
{
return new
Promise(resolve= > setTimeout(resolve, seconds * 1000));
}
; // Format as yyyy - MM - dd

teams = document.querySelectorAll('p-header')
regions = document.querySelectorAll('div[role="region"]')
          // Number
of
groups
to
create
let
regionsToCover = act == -1 ? regions.length: act - 1;
for (let j = 0; j < regionsToCover; j++)
{
region = regions[j]
// Wait
for the new line to be added (might require a short delay if dynamically loaded)
let
numGroups = parseInt(Array.
from

(teams[j].querySelectorAll('span.container'))[3].textContent.match( /\d + / )[0], 10);
let
numHours = parseInt(Array.
from

(teams[j].querySelectorAll('span.container'))[4].textContent.match( /\d + / )[0], 10);
for (let i = 0; i < numGroups * numHours / 2; i++) {
if (i > 0) {
// Click the plus button to add a new line
region.querySelector('button[class="gap-link-img"]').click();
await sleep(0.5)
}
}
let
cycles = numHours / 2;

for (let c = 0; c < cycles; c++){
                                // Calculate the date of the first Sunday after 2 weeks from today
let today = new Date();
let targetDate = addDays(today, 6); // Two weeks from today
while (targetDate.getDay() !== 0) {// 0 means Sunday
targetDate = addDays(targetDate, 1);
}
targetDate = addDays(targetDate, c)
let
formattedDate = String(targetDate.getDate()).padStart(2, '0') + "/" + String(targetDate.getMonth() + 1).padStart(2,
                                                                                                                 '0') + "/" + targetDate.getFullYear()
for (let k =0; k < numGroups; k++){
    team = region.querySelectorAll("tr")[k+1 + c * numGroups]
// num of teams filling
team.querySelector('p-dropdown').querySelector('div[role="button"]').click()
// after few secs
options = document.querySelectorAll("p-dropdownitem");
await sleep(0.5)
options[k].querySelector("li").click()

// Fill the date field
team.querySelector('p-calendar').querySelector('button').click()
await sleep(1)
let dateField = team.querySelectorAll('p-calendar')[0].querySelector('input');
dateField.value = formattedDate;



calendar = document.querySelector("table.p-datepicker-calendar")
days = Array.from (calendar.querySelectorAll("span")).filter(span = > span.textContent.trim() == targetDate.getDate());
dayToSelect = days[days.length - 1]
dayToSelect.click()

// Fill the "משעה" field (16:00)
let
fromHourField = team.querySelectorAll('p-calendar')[1].querySelector('input');
fromHourField.value = '16:00';

// Fill
the
"עד שעה"
field(18: 00)
let
toHourField = team.querySelectorAll('p-calendar')[2].querySelector('input');
toHourField.value = '18:00';

// Check
all
checkboxes in "מקום פעילות"
team.querySelector('p-multiselect').querySelector("span").click()
await sleep(0.5)
team.querySelector('p-multiselect').querySelectorAll('li')[1].click()

// Fill
the
"שם מפעיל"
field
with "תוכנה"
team.querySelector('td.shemMafhil').querySelector("input").value = 'תןכנה'
}

}
region.querySelector('button.save-btn').click()
await sleep(3)
document.querySelectorAll("p-accordiontab")[j + 1].querySelector("a").click()
await sleep(2)
}
}
// Execute
the
function
fillActivityControl();