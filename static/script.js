
document.getElementById('forecastForm').addEventListener('submit', function(event) {
    event.preventDefault();

    const firstPlace = document.getElementById('firstPlace').value;
    const secondPlace = document.getElementById('secondPlace').value;
    const thirdPlace = document.getElementById('thirdPlace').value;
    const percentage = document.getElementById('percentage').value;

    const result = `
        <h2>Your Forecast</h2>
        <p>1st Place: ${firstPlace}</p>
        <p>2nd Place: ${secondPlace}</p>
        <p>3rd Place: ${thirdPlace}</p>
        <p>Percentage of other forecasters selecting the same teams: ${percentage}%</p>
    `;

    document.getElementById('result').innerHTML = result;
});
