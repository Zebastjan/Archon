/**
 * Real-world TypeScript code for testing tree-sitter extraction.
 * Contains diverse TypeScript constructs including interfaces, generics, decorators.
 */

import { useState, useEffect, useCallback } from 'react';
import * as utils from './utils';

// Type aliases
type UserID = string;
type Callback<T> = (data: T) => void;

// Interfaces
interface User {
  id: UserID;
  name: string;
  email?: string;
  createdAt: Date;
}

interface Repository<T> {
  findById(id: string): Promise<T | null>;
  findAll(): Promise<T[]>;
  save(entity: T): Promise<T>;
  delete(id: string): Promise<boolean>;
}

// Generic interface with constraints
interface Comparable<T> {
  compareTo(other: T): number;
}

// Class implementing interface
class UserRepository implements Repository<User> {
  private users: Map<string, User> = new Map();
  private readonly dbUrl: string;

  constructor(dbUrl: string) {
    this.dbUrl = dbUrl;
  }

  async findById(id: string): Promise<User | null> {
    return this.users.get(id) || null;
  }

  async findAll(): Promise<User[]> {
    return Array.from(this.users.values());
  }

  async save(entity: User): Promise<User> {
    this.users.set(entity.id, entity);
    return entity;
  }

  async delete(id: string): Promise<boolean> {
    return this.users.delete(id);
  }

  // Generic method
  async query<T>(sql: string, params?: T[]): Promise<T[]> {
    console.log(`Querying: ${sql}`);
    return [];
  }
}

// Abstract class
abstract class BaseService<T> {
  protected repository: Repository<T>;

  constructor(repository: Repository<T>) {
    this.repository = repository;
  }

  abstract validate(entity: T): boolean;

  async findById(id: string): Promise<T | null> {
    return this.repository.findById(id);
  }
}

// Concrete class with inheritance
class UserService extends BaseService<User> {
  private validators: Array<(user: User) => boolean> = [];

  constructor(repository: UserRepository) {
    super(repository);
  }

  validate(user: User): boolean {
    return !!user.name && !!user.email;
  }

  async createUser(name: string, email: string): Promise<User> {
    const user: User = {
      id: Math.random().toString(),
      name,
      email,
      createdAt: new Date(),
    };

    if (!this.validate(user)) {
      throw new Error('Invalid user data');
    }

    return this.repository.save(user);
  }

  // Arrow function property
  findByEmail = async (email: string): Promise<User | null> => {
    const users = await this.repository.findAll();
    return users.find(u => u.email === email) || null;
  };
}

// Decorated class (Angular/React style)
@Component({
  selector: 'app-user',
  template: '<div>{{user.name}}</div>',
})
class UserComponent {
  @Input()
  user!: User;

  @Output()
  onSave = new EventEmitter<User>();

  private _loading: boolean = false;

  @HostListener('click')
  handleClick(): void {
    this.onSave.emit(this.user);
  }

  get loading(): boolean {
    return this._loading;
  }

  set loading(value: boolean) {
    this._loading = value;
  }
}

// Function declarations
function formatDate(date: Date, format: string = 'YYYY-MM-DD'): string {
  return date.toISOString().split('T')[0];
}

// Async function
async function fetchUsers(apiUrl: string): Promise<User[]> {
  const response = await fetch(`${apiUrl}/users`);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
}

// Generator function
function* idGenerator(): Generator<string, void, unknown> {
  let id = 0;
  while (true) {
    yield `user-${id++}`;
  }
}

// Higher-order function
function memoize<T extends (...args: any[]) => any>(fn: T): T {
  const cache = new Map();
  
  return function (...args: Parameters<T>): ReturnType<T> {
    const key = JSON.stringify(args);
    if (cache.has(key)) {
      return cache.get(key);
    }
    const result = fn(...args);
    cache.set(key, result);
    return result;
  } as T;
}

// Namespace
namespace Validation {
  export interface Validator<T> {
    validate(value: T): boolean;
  }

  export class EmailValidator implements Validator<string> {
    validate(email: string): boolean {
      return email.includes('@');
    }
  }
}

// Enum
enum Status {
  PENDING = 'pending',
  ACTIVE = 'active',
  INACTIVE = 'inactive',
}

// React hooks
function useUser(userId: string) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadUser() {
      setLoading(true);
      try {
        const data = await fetchUsers('/api');
        if (!cancelled) {
          setUser(data.find(u => u.id === userId) || null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err as Error);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadUser();

    return () => {
      cancelled = true;
    };
  }, [userId]);

  const refresh = useCallback(() => {
    setUser(null);
  }, []);

  return { user, loading, error, refresh };
}

// Generic function with constraints
function sortBy<T extends { [K in keyof T]: T[K] }>(
  items: T[],
  key: keyof T
): T[] {
  return [...items].sort((a, b) => {
    if (a[key] < b[key]) return -1;
    if (a[key] > b[key]) return 1;
    return 0;
  });
}

// Conditional types
type NonNullable<T> = T extends null | undefined ? never : T;
type ReturnType<T extends (...args: any[]) => any> = T extends (...args: any[]) => infer R ? R : any;

// Mapped types
type Readonly<T> = {
  readonly [P in keyof T]: T[P];
};

type Partial<T> = {
  [P in keyof T]?: T[P];
};

// Utility functions with overloads
function process(value: string): string;
function process(value: number): number;
function process(value: string | number): string | number {
  if (typeof value === 'string') {
    return value.toUpperCase();
  }
  return value * 2;
}

// Class with static members
class MathUtils {
  static readonly PI: number = 3.14159;
  
  static circleArea(radius: number): number {
    return this.PI * radius * radius;
  }
  
  static randomInt(min: number, max: number): number {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }
}

// Export examples
export { User, UserRepository, UserService };
export type { UserID, Callback };
export default UserComponent;
