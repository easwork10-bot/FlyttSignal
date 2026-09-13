import { api } from "./client";
import type { City } from "./types";
export const getCities = () => api<City[]>("/cities");
