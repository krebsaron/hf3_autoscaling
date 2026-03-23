# HF3 - Autoscaling rövid összefoglaló

## Mit használtam

- Az alap alkalmazás Heroku-n fut (`hf1-webapp-paas`).
- Az automatikus skálázást Hirefire-rel állítottam be, közvetlenül a webes UI-n keresztül.
- A terhelésgeneráláshoz Locustot használtam, külön Heroku alkalmazásból futtatva.

## Az automatikus skálázódás konfigurálása a választott PaaS környezetben

Választott környezet: Heroku + Hirefire.

1. A Heroku alkalmazás dyno típusa Basic helyett Standard lett, hogy támogassa a skálázást.
2. A Hirefire fiókot a Heroku fiókkal összekötöttem, majd kiválasztottam a `hf1-webapp-paas` alkalmazást.
3. Létrehoztam egy Dyno Managert a `web` processzhez.
4. A skálázási stratégia metrikája a Logplex - Requests Per Minute (RPM) lett, mert ennél a laborfeladatnál ez mutatta leglátványosabban a fel- és visszaskálázódást.
5. A szükséges log drain hozzáadásra került Heroku oldalon, hogy a Hirefire megkapja a request alapú metrikát.
6. A dyno menedzsment célállapota: alapterhelésnél 1 dyno, terhelésnél felskálázás 2 dynóra, majd terheléscsökkenés után vissza 1 dynóra.


## Tapasztalat a terheléspróba során

- A Hirefire konfiguráció egyszerű és gyors volt.
- A skálázási metrikának a Requests Per Minute (Logplex) értéket használtam, mert ezzel szemléletesen és megbízhatóan látható az auto skálázódás.
- A terhelés hatására az alkalmazás felskálázódott 1 dynóról 2 dynóra, majd a terhelés csökkenése után visszaskálázódott 1 dynóra.

## Eredmények

- Locust report: [reports/report_1774273829.310681.html](reports/report_1774273829.310681.html)
- Skálázódási bizonyíték (screenshot): [reports/scalingActivity.png](reports/scalingActivity.png)
