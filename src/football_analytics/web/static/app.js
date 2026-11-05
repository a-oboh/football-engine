const competition = document.querySelector("#competition");
const seasons = document.querySelector("#seasons");
const homeTeam = document.querySelector("#home-team");
const awayTeam = document.querySelector("#away-team");
const button = document.querySelector("#forecast");
const message = document.querySelector("#message");
const results = document.querySelector("#results");

let catalogue = [];

async function request(url) {
  const response = await fetch(url);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Unable to load forecast data.");
  return payload;
}

function selectedSeasons() {
  return Array.from(seasons.selectedOptions).map((option) => option.value);
}

function populateSelect(select, values, label) {
  select.replaceChildren(...values.map((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label(value);
    return option;
  }));
}

async function updateTeams() {
  const selected = selectedSeasons();
  if (!selected.length) return;
  const parameters = new URLSearchParams({ competition_code: competition.value });
  selected.forEach((season) => parameters.append("season", season));
  const payload = await request(`/api/teams?${parameters}`);
  populateSelect(homeTeam, payload.teams, (team) => team);
  populateSelect(awayTeam, payload.teams, (team) => team);
  if (payload.teams.length > 1) awayTeam.selectedIndex = 1;
}

function updateSeasons() {
  const item = catalogue.find((entry) => entry.code === competition.value);
  populateSelect(seasons, item.seasons, (season) => season);
  Array.from(seasons.options).forEach((option) => { option.selected = true; });
  return updateTeams();
}

function percent(value) { return `${(value * 100).toFixed(1)}%`; }
function decimal(value) { return value.toFixed(2); }

function market(label, value) {
  return `<article class="market"><p>${label}</p><strong>${percent(value.probability)}</strong><span>Fair odds ${decimal(value.fair_odds)}</span></article>`;
}

function showPrediction(data) {
  const fixture = data.fixture;
  document.querySelector("#fixture-title").textContent = `${fixture.home_team} v ${fixture.away_team}`;
  document.querySelector("#half-time-score").textContent = `${data.half_time.home_goals} - ${data.half_time.away_goals}`;
  document.querySelector("#half-time-probability").textContent = `${percent(data.half_time.probability)} exact-score probability`;
  document.querySelector("#full-time-score").textContent = `${data.full_time.home_goals} - ${data.full_time.away_goals}`;
  document.querySelector("#full-time-probability").textContent = `${percent(data.full_time.probability)} exact-score probability`;
  document.querySelector("#expected-goals").textContent = `${data.expected_goals.home.toFixed(2)} / ${data.expected_goals.away.toFixed(2)}`;
  const markets = data.markets;
  document.querySelector("#markets").innerHTML = [
    market("Home win", markets.home_win), market("Draw", markets.draw),
    market("Away win", markets.away_win), market("Over 2.5 goals", markets.over_2_5_goals),
    market("Under 2.5 goals", markets.under_2_5_goals), market("BTTS: Yes", markets.btts_yes),
    market("BTTS: No", markets.btts_no),
  ].join("");
  results.hidden = false;
}

async function runForecast() {
  message.textContent = "";
  if (!homeTeam.value || !awayTeam.value || homeTeam.value === awayTeam.value) {
    message.textContent = "Choose two different teams.";
    return;
  }
  button.disabled = true;
  button.textContent = "Calculating...";
  try {
    const parameters = new URLSearchParams({
      competition_code: competition.value,
      home_team: homeTeam.value,
      away_team: awayTeam.value,
    });
    selectedSeasons().forEach((season) => parameters.append("season", season));
    showPrediction(await request(`/api/prediction?${parameters}`));
  } catch (error) {
    message.textContent = error.message;
  } finally {
    button.disabled = false;
    button.textContent = "Run forecast";
  }
}

async function initialise() {
  try {
    catalogue = await request("/api/competitions");
    populateSelect(competition, catalogue, (item) => item.name);
    competition.replaceChildren(...catalogue.map((item) => {
      const option = document.createElement("option");
      option.value = item.code;
      option.textContent = item.name;
      return option;
    }));
    await updateSeasons();
  } catch (error) {
    message.textContent = error.message;
  }
}

competition.addEventListener("change", updateSeasons);
seasons.addEventListener("change", updateTeams);
button.addEventListener("click", runForecast);
initialise();
