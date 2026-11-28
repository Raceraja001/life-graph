import isOdd from "is-odd";

export const parity = (n: number): "odd" | "even" => (isOdd(n) ? "odd" : "even");
