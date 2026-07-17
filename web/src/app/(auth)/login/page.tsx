"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { supabase } from "@/lib/supabase";
import { useAuthSession } from "@/hooks/useAuthSession";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";

const loginSchema = z.object({
  email: z.string().min(1, "Informe seu e-mail.").email("E-mail inválido."),
  senha: z.string().min(6, "A senha deve ter ao menos 6 caracteres."),
});

type LoginForm = z.infer<typeof loginSchema>;

/**
 * Login mínimo (e-mail/senha) pra permitir testar as telas autenticadas
 * localmente. Login social (Google OAuth, conforme CLAUDE.md) e cadastro
 * completo com aceite de termos ficam para uma spec própria de
 * onboarding — decisão de menor escopo, reportada no fechamento da
 * entrega.
 */
export default function LoginPage() {
  const router = useRouter();
  const { session, carregando: carregandoSessao } = useAuthSession();
  const [modo, setModo] = useState<"entrar" | "cadastrar">("entrar");
  const [enviando, setEnviando] = useState(false);
  const [erroApi, setErroApi] = useState<string | null>(null);
  const [mensagemCadastro, setMensagemCadastro] = useState<string | null>(null);

  useEffect(() => {
    if (!carregandoSessao && session) {
      router.replace("/peso");
    }
  }, [carregandoSessao, session, router]);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(dados: LoginForm) {
    setEnviando(true);
    setErroApi(null);
    setMensagemCadastro(null);

    if (modo === "entrar") {
      const { error } = await supabase.auth.signInWithPassword({
        email: dados.email,
        password: dados.senha,
      });
      setEnviando(false);
      if (error) {
        setErroApi("E-mail ou senha incorretos.");
        return;
      }
      router.replace("/peso");
    } else {
      const { error } = await supabase.auth.signUp({
        email: dados.email,
        password: dados.senha,
      });
      setEnviando(false);
      if (error) {
        setErroApi("Não foi possível criar sua conta. Tente novamente.");
        return;
      }
      setMensagemCadastro("Conta criada. Verifique seu e-mail para confirmar o acesso.");
    }
  }

  if (carregandoSessao) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-11 w-full" />
        <Skeleton className="h-11 w-full" />
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold">Delta.AI</h1>
      <p className="mb-6 text-sm text-neutral-500 dark:text-neutral-400">
        {modo === "entrar" ? "Entre na sua conta." : "Crie sua conta."}
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div>
          <Label htmlFor="email">E-mail</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={errors.email ? "true" : undefined}
            aria-describedby={errors.email ? "email-erro" : undefined}
            {...register("email")}
          />
          {errors.email && (
            <p id="email-erro" className="mt-1.5 text-sm text-rose-600 dark:text-rose-400">
              {errors.email.message}
            </p>
          )}
        </div>

        <div>
          <Label htmlFor="senha">Senha</Label>
          <Input
            id="senha"
            type="password"
            autoComplete={modo === "entrar" ? "current-password" : "new-password"}
            aria-invalid={errors.senha ? "true" : undefined}
            aria-describedby={errors.senha ? "senha-erro" : undefined}
            {...register("senha")}
          />
          {errors.senha && (
            <p id="senha-erro" className="mt-1.5 text-sm text-rose-600 dark:text-rose-400">
              {errors.senha.message}
            </p>
          )}
        </div>

        {erroApi && <Alert variant="erro">{erroApi}</Alert>}
        {mensagemCadastro && <Alert variant="sucesso">{mensagemCadastro}</Alert>}

        <Button type="submit" className="w-full" disabled={enviando}>
          {enviando ? "Enviando..." : modo === "entrar" ? "Entrar" : "Criar conta"}
        </Button>
      </form>

      <button
        type="button"
        onClick={() => {
          setModo(modo === "entrar" ? "cadastrar" : "entrar");
          setErroApi(null);
          setMensagemCadastro(null);
        }}
        className="mt-4 text-sm text-acento-600 hover:underline dark:text-acento-500"
      >
        {modo === "entrar" ? "Não tem conta? Criar uma agora." : "Já tem conta? Entrar."}
      </button>
    </div>
  );
}
