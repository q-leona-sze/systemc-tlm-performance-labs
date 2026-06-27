module banked_memory_controller #(
  parameter int unsigned BANK_COUNT = 4,
  parameter int unsigned INTERLEAVE_BYTES = 64,
  parameter int unsigned SERVICE_LATENCY_CYCLES = 10,
  parameter int unsigned QUEUE_DEPTH = 8
) (
  input  logic        clk,
  input  logic        reset,
  input  logic        valid,
  input  logic [63:0] addr,
  input  logic        is_write,
  output logic        ready,
  output logic        accepted,
  output logic        done,
  output logic [31:0] bank_id,
  output logic [31:0] latency_cycles
);

  logic [63:0] cycle_counter;
  logic [31:0] outstanding_count [BANK_COUNT];
  logic [31:0] head_index [BANK_COUNT];
  logic [31:0] tail_index [BANK_COUNT];
  logic [63:0] completion_cycle [BANK_COUNT][QUEUE_DEPTH];
  logic [63:0] bank_next_available_cycle [BANK_COUNT];
  logic [63:0] bank_id_wide;
  logic [31:0] effective_outstanding;
  logic [63:0] service_start_cycle;
  logic [63:0] accepted_done_cycle;
  logic [63:0] command_latency_adjust;
  logic [63:0] latency_cycles_wide;

  localparam logic [63:0] BANK_COUNT_64 = 64'(BANK_COUNT);
  localparam logic [63:0] INTERLEAVE_BYTES_64 = 64'(INTERLEAVE_BYTES);
  localparam logic [63:0] SERVICE_LATENCY_CYCLES_64 =
      64'(SERVICE_LATENCY_CYCLES);

  function automatic logic [31:0] next_queue_index(input logic [31:0] index);
    if (index + 1 >= QUEUE_DEPTH) begin
      next_queue_index = 32'd0;
    end else begin
      next_queue_index = index + 1;
    end
  endfunction

  always_comb begin
    bank_id_wide = 64'd0;
    bank_id = 32'd0;
    if (BANK_COUNT_64 > 64'd0 && INTERLEAVE_BYTES_64 > 64'd0) begin
      bank_id_wide = ((addr / INTERLEAVE_BYTES_64) % BANK_COUNT_64);
      bank_id = bank_id_wide[31:0];
    end

    effective_outstanding = outstanding_count[bank_id];
    if (outstanding_count[bank_id] > 0 &&
        completion_cycle[bank_id][head_index[bank_id]] <= cycle_counter) begin
      effective_outstanding = outstanding_count[bank_id] - 1;
    end

    ready = (effective_outstanding < QUEUE_DEPTH);

    if (bank_next_available_cycle[bank_id] > cycle_counter) begin
      service_start_cycle = bank_next_available_cycle[bank_id];
    end else begin
      service_start_cycle = cycle_counter;
    end
    command_latency_adjust = is_write ? 64'd0 : 64'd0;
    accepted_done_cycle =
        service_start_cycle + SERVICE_LATENCY_CYCLES_64 + command_latency_adjust;
    latency_cycles_wide = accepted_done_cycle - cycle_counter;

    if (ready) begin
      latency_cycles = latency_cycles_wide[31:0];
    end else begin
      latency_cycles = 32'd0;
    end
  end

  always_ff @(posedge clk) begin
    if (reset) begin
      cycle_counter <= 64'd0;
      accepted <= 1'b0;
      done <= 1'b0;
      for (int bank = 0; bank < BANK_COUNT; bank++) begin
        outstanding_count[bank] <= 32'd0;
        head_index[bank] <= 32'd0;
        tail_index[bank] <= 32'd0;
        bank_next_available_cycle[bank] <= 64'd0;
        for (int slot = 0; slot < QUEUE_DEPTH; slot++) begin
          completion_cycle[bank][slot] <= 64'd0;
        end
      end
    end else begin
      accepted <= 1'b0;
      done <= 1'b0;

      for (int bank = 0; bank < BANK_COUNT; bank++) begin
        if (outstanding_count[bank] > 0 &&
            completion_cycle[bank][head_index[bank]] <= cycle_counter) begin
          outstanding_count[bank] <= outstanding_count[bank] - 1;
          head_index[bank] <= next_queue_index(head_index[bank]);
          done <= 1'b1;
        end
      end

      if (valid && ready) begin
        completion_cycle[bank_id][tail_index[bank_id]] <= accepted_done_cycle;
        tail_index[bank_id] <= next_queue_index(tail_index[bank_id]);
        outstanding_count[bank_id] <= effective_outstanding + 1;
        bank_next_available_cycle[bank_id] <= accepted_done_cycle;
        accepted <= 1'b1;
      end

      cycle_counter <= cycle_counter + 64'd1;
    end
  end

endmodule
