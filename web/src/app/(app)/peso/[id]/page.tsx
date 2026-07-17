"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { usePesagem, useEditarPesagem, useExcluirPesagem } from "@/hooks/usePesagens";
import { InputMedida } from "@/components/domain/InputMedida";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { paraInputDatetimeLocal } from "@/lib/format";

const editarPesagemSchema = z
  .object({
    peso_kg: z.coerce
      .number({ invalid_type_error: "Informe um peso válido." })
      .min(20, "O peso deve estar entre 20 e 400 kg.")
      .max(400, "O peso deve estar entre 20 e 400 kg."),
    registrada_em: z.string().min(1, "Informe a data e hora da pesagem."),
  })
  .refine((dados) => new Date(dados.registrada_em) <= new Date(), {
    message: "Não é possível registrar uma data futura.",
    path: ["registrada_em"],
  });

type EditarPesagemForm = z.infer<typeof editarPesagemSchema>;

export default function EditarPesagemPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { pesagem, carregando, erro } = usePesagem(params.id);
  const editarPesagem = useEditarPesagem(params.id);
  const excluirPesagem = useExcluirPesagem();
  const [erroSubmissao, setErroSubmissao] = useState<string | null>(null);
  const [excluindo, setExcluindo] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<EditarPesagemForm>({ resolver: zodResolver(editarPesagemSchema) });

  useEffect(() => {
    if (pesagem) {
      reset({
        peso_kg: pesagem.peso_kg,
        registrada_em: paraInputDatetimeLocal(new Date(pesagem.registrada_em)),
      });
    }
  }, [pesagem, reset]);

  async function onSubmit(dados: EditarPesagemForm) {
    setErroSubmissao(null);
    try {
      await editarPesagem.mutateAsync({
        peso_kg: dados.peso_kg,
        registrada_em: new Date(dados.registrada_em).toISOString(),
      });
      router.push("/peso");
    } catch (erro) {
      if (erro instanceof ApiError && erro.status === 404) {
        setErroSubmissao("Esta pesagem não existe mais.");
      } else {
        setErroSubmissao("Não foi possível salvar as alterações. Tente novamente.");
      }
    }
  }

  async function excluir() {
    if (!window.confirm("Excluir esta pesagem? Essa ação não pode ser desfeita.")) return;
    setExcluindo(true);
    try {
      await excluirPesagem.mutateAsync(params.id);
      router.push("/peso");
    } catch {
      setErroSubmissao("Não foi possível excluir esta pesagem agora.");
      setExcluindo(false);
    }
  }

  if (carregando) {
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Carregando pesagem">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (erro) {
    return <Alert variant="erro">Não foi possível carregar esta pesagem agora.</Alert>;
  }

  if (!pesagem) {
    return <Alert variant="info">Esta pesagem não foi encontrada.</Alert>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Editar pesagem</h1>
      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <InputMedida
            id="peso_kg"
            label="Peso"
            unidade="kg"
            erro={errors.peso_kg?.message}
            {...register("peso_kg")}
          />
          <div>
            <Label htmlFor="registrada_em">Quando você se pesou</Label>
            <Input
              id="registrada_em"
              type="datetime-local"
              max={paraInputDatetimeLocal(new Date())}
              aria-invalid={errors.registrada_em ? "true" : undefined}
              aria-describedby={errors.registrada_em ? "registrada_em-erro" : undefined}
              {...register("registrada_em")}
            />
            {errors.registrada_em && (
              <p
                id="registrada_em-erro"
                className="mt-1.5 text-sm text-rose-600 dark:text-rose-400"
              >
                {errors.registrada_em.message}
              </p>
            )}
          </div>
          {erroSubmissao && <Alert variant="erro">{erroSubmissao}</Alert>}
          <div className="flex gap-2">
            <Button type="submit" disabled={isSubmitting} className="flex-1">
              {isSubmitting ? "Salvando..." : "Salvar alterações"}
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={excluir}
              disabled={excluindo}
            >
              {excluindo ? "Excluindo..." : "Excluir"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
