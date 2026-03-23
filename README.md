# HF3 - Autoscaling rövid összefoglaló

## Mit használtam

- Az alap alkalmazás Heroku-n fut (`hf1-webapp-paas`).
- Az automatikus skálázást Hirefire-rel állítottam be, közvetlenül a webes UI-n keresztül.
- A terhelésgeneráláshoz Locustot használtam, külön Heroku alkalmazásból futtatva.

## Tapasztalat a terheléspróba során

- A Hirefire konfiguráció egyszerű és gyors volt.
- A skálázási metrikának a Requests Per Minute (Logplex) értéket használtam, mert ezzel szemléletesen és megbízhatóan látható az auto skálázódás.
- A terhelés hatására az alkalmazás felskálázódott 1 dynóról 2 dynóra, majd a terhelés csökkenése után visszaskálázódott 1 dynóra.

## Eredmények

- Locust report: [reports/report_1774273829.310681.html](reports/report_1774273829.310681.html)
- Skálázódási bizonyíték (screenshot): [reports/scalingActivity.png](reports/scalingActivity.png)
