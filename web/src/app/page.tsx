import { redirect } from "next/navigation";

/**
 * Raiz do app. Não há ainda uma home "hoje/" (fora do escopo desta
 * entrega — ver relatório do frontend-engineer); redireciona pra tela de
 * peso, que hoje é o fluxo mais central implementado. `(app)/layout.tsx`
 * garante que só usuário autenticado chega lá.
 */
export default function RootPage() {
  redirect("/peso");
}
