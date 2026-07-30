export type User = {
  id: string
  username: string
  email: string | null
  role: string
  created_at: string
}

export type MeResponse = {
  user: User
}
