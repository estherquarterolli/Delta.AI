"use client";

import { useId, useState } from "react";
import { Card } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { useAtualizarCondicoesSaude } from "@/hooks/usePerfil";

/**
 * Tela de edição de perfil. Hoje só existe o campo `esta_gestante`
 * (adicionado por specs/2026-07-17-calculo-imc.md) — altura, data de
 * nascimento e demais dados de perfil ainda não têm endpoint de escrita
 * no backend, então não são editáveis aqui ainda (ver relatório de
 * lacunas do frontend-engineer).
 *
 * Não existe hoje um `GET` dedicado para ler `condicoes_saude.esta_gestante`
 * (só é lido internamente por `GET /perfil/imc`) — por isso o toggle
 * abaixo é só um controle de escrita: começa em `false`/não preenchido a
 * cada carregamento da tela, e passa a refletir o valor recém-salvo
 * depois de um `PATCH /perfil/condicoes-saude` bem-sucedido, não um
 * estado lido do servidor.
 */
export default function PerfilPage() {
  const [estaGestante, setEstaGestante] = useState(false);
  const [salvoComSucesso, setSalvoComSucesso] = useState(false);
  const switchId = useId();
  const atualizarCondicoesSaude = useAtualizarCondicoesSaude();

  async function handleSalvar() {
    setSalvoComSucesso(false);
    try {
      const resposta = await atualizarCondicoesSaude.mutateAsync({
        esta_gestante: estaGestante,
      });
      setEstaGestante(resposta.esta_gestante);
      setSalvoComSucesso(true);
    } catch {
      // erro fica disponível em atualizarCondicoesSaude.error, tratado abaixo.
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Perfil</h1>

      <Card>
        <div className="flex items-center justify-between gap-4">
          <div>
            <label htmlFor={switchId} className="font-medium">
              Você está gestante atualmente?
            </label>
            <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
              Perguntamos isso porque a gestação muda como calculamos indicadores de
              saúde do app, como o IMC — durante a gestação, a faixa padrão de IMC não
              é um indicador adequado.
            </p>
          </div>
          <Switch
            id={switchId}
            checked={estaGestante}
            onChange={(e) => {
              setEstaGestante(e.target.checked);
              setSalvoComSucesso(false);
            }}
            aria-label="Você está gestante atualmente?"
          />
        </div>

        {salvoComSucesso && (
          <Alert variant="sucesso" className="mt-4">
            Resposta salva.
          </Alert>
        )}

        {atualizarCondicoesSaude.isError && (
          <Alert variant="erro" className="mt-4">
            Não foi possível salvar sua resposta agora. Tente novamente.
          </Alert>
        )}

        <Button
          className="mt-4 w-full"
          onClick={handleSalvar}
          disabled={atualizarCondicoesSaude.isPending}
        >
          {atualizarCondicoesSaude.isPending ? "Salvando..." : "Salvar"}
        </Button>
      </Card>

      <p className="text-xs text-neutral-500 dark:text-neutral-400">
        Altura e data de nascimento ainda não podem ser editadas por aqui — essa parte
        do perfil também depende de um endpoint de backend que ainda não existe.
      </p>
    </div>
  );
}
