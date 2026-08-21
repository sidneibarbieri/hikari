/* Contagem regressiva da faixa de horários da competição.
 *
 * O servidor entrega quantos segundos faltavam no momento em que a página foi
 * montada. O relógio do navegador do competidor pode estar errado, então a
 * contagem parte desse número e desconta o tempo decorrido aqui, em vez de
 * comparar com o horário de término. */
(function () {
  "use strict";

  var UM_SEGUNDO = 1000;

  function doisDigitos(valor) {
    return valor < 10 ? "0" + valor : String(valor);
  }

  function formatar(segundos) {
    var horas = Math.floor(segundos / 3600);
    var minutos = Math.floor((segundos % 3600) / 60);
    return doisDigitos(horas) + ":" + doisDigitos(minutos) + ":" + doisDigitos(segundos % 60);
  }

  function iniciar(faixa) {
    var mostrador = faixa.querySelector("[data-hikari-window-clock]");
    if (!mostrador) {
      return;
    }
    var restante = parseInt(faixa.getAttribute("data-hikari-window-remaining"), 10);
    if (isNaN(restante)) {
      return;
    }
    var pausada = faixa.classList.contains("hikari-window--paused");
    var abertura = Date.now();

    function desenhar() {
      var decorrido = pausada ? 0 : Math.floor((Date.now() - abertura) / UM_SEGUNDO);
      var falta = Math.max(restante - decorrido, 0);
      mostrador.textContent = formatar(falta);
      if (falta === 0 && !pausada) {
        window.clearInterval(relogio);
      }
    }

    var relogio = window.setInterval(desenhar, UM_SEGUNDO);
    desenhar();
  }

  document.addEventListener("DOMContentLoaded", function () {
    var faixas = document.querySelectorAll("[data-hikari-window-remaining]");
    for (var i = 0; i < faixas.length; i += 1) {
      iniciar(faixas[i]);
    }
  });
})();
