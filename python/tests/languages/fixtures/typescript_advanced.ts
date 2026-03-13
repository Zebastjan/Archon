/**
 * Advanced TypeScript patterns for testing edge cases.
 * Includes complex generics, mapped types, conditional types, and more.
 */

// ============================================================================
// Conditional and Mapped Types
// ============================================================================

type NonNullable<T> = T extends null | undefined ? never : T;

type DeepReadonly<T> = {
  readonly [P in keyof T]: T[P] extends object ? DeepReadonly<T[P]> : T[P];
};

type RequiredBy<T, K extends keyof T> = Required<Pick<T, K>> & Partial<Omit<T, K>>;

type EventPayload<T extends string> = T extends 'click' 
  ? { x: number; y: number }
  : T extends 'input'
  ? { value: string }
  : never;

// ============================================================================
// Complex Generics with Constraints
// ============================================================================

interface Entity {
  id: string;
  createdAt: Date;
}

class Repository<T extends Entity> {
  private items: Map<string, T> = new Map();

  async findById(id: string): Promise<T | undefined> {
    return this.items.get(id);
  }

  async save(entity: T): Promise<T> {
    this.items.set(entity.id, entity);
    return entity;
  }

  async findAll(options?: {
    limit?: number;
    offset?: number;
    orderBy?: keyof T;
  }): Promise<T[]> {
    const items = Array.from(this.items.values());
    if (options?.limit) {
      return items.slice(options.offset || 0, options.limit);
    }
    return items;
  }
}

// Generic with multiple type parameters
class Service<T extends Entity, D extends Record<string, unknown>> {
  constructor(
    private repository: Repository<T>,
    private defaults: D
  ) {}

  async create(data: Omit<T, 'id' | 'createdAt'> & Partial<D>): Promise<T> {
    throw new Error('Not implemented');
  }
}

// ============================================================================
// Discriminated Unions
// ============================================================================

interface Circle {
  kind: 'circle';
  radius: number;
}

interface Square {
  kind: 'square';
  side: number;
}

interface Triangle {
  kind: 'triangle';
  base: number;
  height: number;
}

type Shape = Circle | Square | Triangle;

function calculateArea(shape: Shape): number {
  switch (shape.kind) {
    case 'circle':
      return Math.PI * shape.radius ** 2;
    case 'square':
      return shape.side ** 2;
    case 'triangle':
      return (shape.base * shape.height) / 2;
    default:
      const _exhaustive: never = shape;
      return _exhaustive;
  }
}

// ============================================================================
// Template Literal Types
// ============================================================================

type EventName<T extends string> = `on${Capitalize<T>}`;

type CSSProperty = `-${string}` | string;

type DataAttribute = `data-${string}`;

interface Props {
  [key: DataAttribute]: string;
}

// ============================================================================
// Mixins and Intersection Types
// ============================================================================

type Constructor<T = {}> = new (...args: any[]) => T;

function Timestamped<TBase extends Constructor>(Base: TBase) {
  return class extends Base {
    timestamp = new Date();
    
    getTimestamp() {
      return this.timestamp;
    }
  };
}

function Activatable<TBase extends Constructor>(Base: TBase) {
  return class extends Base {
    isActive = false;
    
    toggle() {
      this.isActive = !this.isActive;
    }
  };
}

class User {
  constructor(public name: string) {}
}

const TimestampedActivatableUser = Timestamped(Activatable(User));

// ============================================================================
// Decorators with Metadata
// ============================================================================

const metadataKey = Symbol('design:paramtypes');

function Injectable() {
  return function <T extends new (...args: any[]) => {}>(target: T) {
    Reflect.defineMetadata(metadataKey, [], target);
    return target;
  };
}

function Inject(token: string) {
  return function (target: any, propertyKey: string | symbol, parameterIndex: number) {
    const existingTokens = Reflect.getMetadata('inject:tokens', target) || [];
    existingTokens[parameterIndex] = token;
    Reflect.defineMetadata('inject:tokens', existingTokens, target);
  };
}

@Injectable()
class DatabaseService {
  constructor(@Inject('DB_CONNECTION') private connection: string) {}
  
  async query<T>(sql: string): Promise<T[]> {
    return [];
  }
}

// Method and property decorators
function Memoize() {
  return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value;
    const cache = new Map();
    
    descriptor.value = function (...args: any[]) {
      const key = JSON.stringify(args);
      if (cache.has(key)) {
        return cache.get(key);
      }
      const result = originalMethod.apply(this, args);
      cache.set(key, result);
      return result;
    };
  };
}

function Required() {
  return function (target: any, propertyKey: string) {
    // Validation logic
  };
}

// ============================================================================
// Advanced React Patterns
// ============================================================================

import React, { 
  useState, 
  useEffect, 
  useCallback, 
  useMemo, 
  useRef,
  useReducer,
  useContext,
  createContext,
  forwardRef,
  useImperativeHandle
} from 'react';

// Generic component
interface ListProps<T> {
  items: T[];
  renderItem: (item: T) => React.ReactNode;
  keyExtractor: (item: T) => string;
}

function List<T>({ items, renderItem, keyExtractor }: ListProps<T>) {
  return (
    <ul>
      {items.map(item => (
        <li key={keyExtractor(item)}>{renderItem(item)}</li>
      ))}
    </ul>
  );
}

// Context with default value
interface ThemeContextType {
  theme: 'light' | 'dark';
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: 'light',
  toggleTheme: () => {},
});

// Custom hook with generic
function useApi<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    
    async function fetchData() {
      setLoading(true);
      try {
        const response = await fetch(url);
        const result = await response.json() as T;
        if (!cancelled) {
          setData(result);
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

    fetchData();

    return () => {
      cancelled = true;
    };
  }, [url]);

  return { data, loading, error, refetch: () => setData(null) };
}

// Forward ref with generic
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
}

const FancyInput = forwardRef<HTMLInputElement, InputProps>(
  ({ label, ...props }, ref) => {
    return (
      <label>
        {label}
        <input ref={ref} {...props} />
      </label>
    );
  }
);

// ============================================================================
// Utility Types and Type Guards
// ============================================================================

function isString(value: unknown): value is string {
  return typeof value === 'string';
}

function isArray<T>(value: unknown): value is T[] {
  return Array.isArray(value);
}

function assertDefined<T>(value: T | undefined | null): asserts value is T {
  if (value === undefined || value === null) {
    throw new Error('Value is not defined');
  }
}

// Branded types for type safety
type UserId = string & { __brand: 'UserId' };
type OrderId = string & { __brand: 'OrderId' };

function createUserId(id: string): UserId {
  return id as UserId;
}

function createOrderId(id: string): OrderId {
  return id as OrderId;
}

// ============================================================================
// Async Iterators and Generators
// ============================================================================

async function* paginatedAPI<T>(
  endpoint: string,
  pageSize: number
): AsyncGenerator<T[], void, unknown> {
  let page = 1;
  let hasMore = true;

  while (hasMore) {
    const response = await fetch(`${endpoint}?page=${page}&size=${pageSize}`);
    const data = await response.json() as T[];
    
    if (data.length === 0) {
      hasMore = false;
    } else {
      yield data;
      page++;
    }
  }
}

// ============================================================================
// Namespace and Module Patterns
// ============================================================================

namespace Validation {
  export interface Schema<T> {
    validate(value: unknown): value is T;
  }

  export class StringSchema implements Schema<string> {
    validate(value: unknown): value is string {
      return typeof value === 'string';
    }
  }

  export class ObjectSchema<T> implements Schema<T> {
    constructor(private shape: { [K in keyof T]: Schema<T[K]> }) {}

    validate(value: unknown): value is T {
      if (typeof value !== 'object' || value === null) {
        return false;
      }
      // Simplified validation
      return true;
    }
  }
}

// ============================================================================
// Function Overloads
// ============================================================================

interface ParsedDate {
  year: number;
  month: number;
  day: number;
}

function parse(input: string): ParsedDate;
function parse(input: number): Date;
function parse(input: string | number): ParsedDate | Date {
  if (typeof input === 'string') {
    const [year, month, day] = input.split('-').map(Number);
    return { year, month, day };
  }
  return new Date(input);
}

// ============================================================================
// Abstract Classes and Interfaces
// ============================================================================

abstract class BaseController {
  abstract handleRequest(req: Request): Promise<Response>;
  
  protected log(message: string): void {
    console.log(`[${this.constructor.name}] ${message}`);
  }
}

abstract class CRUDController<T extends Entity> extends BaseController {
  abstract create(data: Omit<T, 'id'>): Promise<T>;
  abstract read(id: string): Promise<T | null>;
  abstract update(id: string, data: Partial<T>): Promise<T>;
  abstract delete(id: string): Promise<void>;
  
  async handleRequest(req: Request): Promise<Response> {
    // Common request handling logic
    return new Response();
  }
}

// ============================================================================
// Type-only Imports and Exports
// ============================================================================

type { Entity } from './types';

export type { 
  Shape, 
  EventPayload, 
  ListProps,
  Repository,
  Service 
};

export { 
  calculateArea,
  Timestamped,
  Activatable,
  useApi,
  List,
  Validation
};

export default class MainService {
  // Main export
}
