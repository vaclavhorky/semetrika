# Semetrika

Semetrika je program, který metricky rozebírá latinský hexametr.

## Ovládání souboru app.py

 * vstup: není nutné, aby v něm byly označeny délky samohlásek, ale musí se v něm rozlišovat *u* a *v*
   1. `-i`/`--input` [cesta k souboru s hexametry]
   2. jinak: čti ze standardního vstupu

 * `--brevize`: považuj samohlásky s neoznačenou délkou (tj. bez šikmých/ležatých čárek) za krátké

 * `--nolengths`: nepokoušej se před měřením doplnit délky (ty se Semetrika naučila z jednoznačně změřených hexametrů z rozsáhlého korpusu básní)

