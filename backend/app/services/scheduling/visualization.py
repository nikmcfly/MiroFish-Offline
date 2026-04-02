"""
Schedule Visualization and Reporting

Creates Gantt charts, dashboards, and reports for shop floor scheduling.
Outputs JSON for frontend visualization libraries.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import colorsys

from .models import Schedule, ScheduleEntry, Machine, MachineType, Job


@dataclass
class GanttData:
    """Data structure for Gantt chart visualization"""

    tasks: List[Dict[str, Any]] = field(default_factory=list)
    resources: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: List[Dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "tasks": self.tasks,
                "resources": self.resources,
                "dependencies": self.dependencies,
            },
            indent=2,
            default=str,
        )


class ScheduleVisualizer:
    """
    Creates visualizations from schedules

    Generates data for:
    - Gantt charts (machine timeline)
    - Resource utilization heatmaps
    - Job flow diagrams
    - Bottleneck identification
    """

    # Color scheme for machine types
    MACHINE_COLORS = {
        MachineType.LASER: "#FF6B6B",  # Red
        MachineType.PRESSBRAKE: "#4ECDC4",  # Teal
        MachineType.WELDING: "#FFE66D",  # Yellow
        MachineType.POLISHING: "#95E1D3",  # Mint
        MachineType.ASSEMBLY: "#F38181",  # Coral
        MachineType.SHIPPING: "#AA96DA",  # Purple
    }

    def __init__(self, schedule: Schedule):
        self.schedule = schedule
        self.logger = self._get_logger()

    def _get_logger(self):
        from ....utils.logger import get_logger

        return get_logger("mirofish.scheduling.ScheduleVisualizer")

    def generate_gantt_data(self) -> GanttData:
        """
        Generate Gantt chart data

        Returns data structure compatible with most Gantt chart libraries
        (DHTMLX Gantt, Google Charts, vis-timeline, etc.)
        """
        gantt = GanttData()

        # Group entries by machine
        machine_entries = {}
        for entry in self.schedule.entries:
            if entry.machine_id not in machine_entries:
                machine_entries[entry.machine_id] = []
            machine_entries[entry.machine_id].append(entry)

        # Create resource list (machines)
        for machine_id in machine_entries.keys():
            gantt.resources.append(
                {"id": machine_id, "name": f"Machine {machine_id}", "type": "machine"}
            )

        # Create task list
        task_id_map = {}  # Maps (job_id, op_id) to task_id

        for machine_id, entries in machine_entries.items():
            for idx, entry in enumerate(entries):
                task_id = f"task_{entry.job_id}_{entry.operation_id}"
                task_id_map[(entry.job_id, entry.operation_id)] = task_id

                # Determine color based on status
                color = self._get_color_for_status(entry.status.value)

                gantt.tasks.append(
                    {
                        "id": task_id,
                        "text": f"{entry.job_id} - {entry.operation_id}",
                        "start_date": entry.start_time.isoformat(),
                        "end_date": entry.end_time.isoformat(),
                        "duration": entry.get_duration(),
                        "resource_id": machine_id,
                        "progress": 1.0 if entry.status.value == "complete" else 0,
                        "color": color,
                        "job_id": entry.job_id,
                        "operation_id": entry.operation_id,
                        "status": entry.status.value,
                    }
                )

        # Create dependencies (precedence constraints)
        for entry in self.schedule.entries:
            # Find job and operation
            job_id = entry.job_id
            op_id = entry.operation_id

            # Add dependencies to predecessors
            # This would need job.operation.predecessors
            # Simplified: add parent-child within same job
            pass

        return gantt

    def _get_color_for_status(self, status: str) -> str:
        """Get color for task status"""
        colors = {
            "pending": "#95A5A6",  # Gray
            "queued": "#3498DB",  # Blue
            "setup": "#F39C12",  # Orange
            "running": "#27AE60",  # Green
            "complete": "#2ECC71",  # Light green
            "blocked": "#E74C3C",  # Red
        }
        return colors.get(status, "#95A5A6")

    def generate_machine_timeline(self) -> Dict[str, Any]:
        """
        Generate timeline data for each machine

        Shows what each machine is doing over time.
        """
        timelines = {}

        for entry in self.schedule.entries:
            machine_id = entry.machine_id

            if machine_id not in timelines:
                timelines[machine_id] = []

            timelines[machine_id].append(
                {
                    "start": entry.start_time.isoformat(),
                    "end": entry.end_time.isoformat(),
                    "job": entry.job_id,
                    "operation": entry.operation_id,
                    "duration": entry.get_duration(),
                    "color": self.MACHINE_COLORS.get(
                        self._infer_machine_type(machine_id), "#95A5A6"
                    ),
                }
            )

        return timelines

    def _infer_machine_type(self, machine_id: str) -> MachineType:
        """Infer machine type from ID (simplified)"""
        id_lower = machine_id.lower()
        if "laser" in id_lower:
            return MachineType.LASER
        elif "press" in id_lower or "brake" in id_lower:
            return MachineType.PRESSBRAKE
        elif "weld" in id_lower:
            return MachineType.WELDING
        elif "polish" in id_lower:
            return MachineType.POLISHING
        elif "assembl" in id_lower:
            return MachineType.ASSEMBLY
        elif "ship" in id_lower:
            return MachineType.SHIPPING
        return MachineType.LASER

    def generate_utilization_heatmap(self, window_hours: int = 24) -> Dict[str, Any]:
        """
        Generate utilization heatmap data

        Shows machine utilization by hour
        """
        if not self.schedule.entries:
            return {"hours": [], "machines": [], "values": []}

        # Determine time range
        start_time = min(e.start_time for e in self.schedule.entries)
        end_time = max(e.end_time for e in self.schedule.entries)

        # Create hourly buckets
        hours = []
        current = start_time
        while current < end_time:
            hours.append(current)
            current += timedelta(hours=1)

        # Get unique machines
        machines = sorted(set(e.machine_id for e in self.schedule.entries))

        # Calculate utilization per machine per hour
        values = []
        for machine_id in machines:
            machine_values = []
            machine_entries = [
                e for e in self.schedule.entries if e.machine_id == machine_id
            ]

            for hour in hours:
                hour_end = hour + timedelta(hours=1)

                # Calculate busy time in this hour
                busy_minutes = 0
                for entry in machine_entries:
                    # Overlap between entry and hour
                    overlap_start = max(entry.start_time, hour)
                    overlap_end = min(entry.end_time, hour_end)

                    if overlap_start < overlap_end:
                        busy_minutes += (
                            overlap_end - overlap_start
                        ).total_seconds() / 60

                # Utilization percentage
                utilization = min(100, (busy_minutes / 60) * 100)
                machine_values.append(int(utilization))

            values.append(machine_values)

        return {
            "hours": [h.isoformat() for h in hours],
            "machines": machines,
            "values": values,
        }

    def generate_job_flow(self, job_id: str) -> Dict[str, Any]:
        """
        Generate flow diagram data for a specific job

        Shows the job's path through machines with timing.
        """
        job_entries = [e for e in self.schedule.entries if e.job_id == job_id]

        if not job_entries:
            return {"error": f"Job {job_id} not found"}

        # Sort by start time
        job_entries.sort(key=lambda e: e.start_time)

        flow = {"job_id": job_id, "operations": []}

        for idx, entry in enumerate(job_entries):
            wait_time = 0
            if idx > 0:
                prev_end = job_entries[idx - 1].end_time
                wait_time = (entry.start_time - prev_end).total_seconds() / 60

            flow["operations"].append(
                {
                    "sequence": idx + 1,
                    "operation_id": entry.operation_id,
                    "machine_id": entry.machine_id,
                    "start": entry.start_time.isoformat(),
                    "end": entry.end_time.isoformat(),
                    "duration": entry.get_duration(),
                    "wait_time": int(wait_time),
                    "status": entry.status.value,
                }
            )

        return flow

    def generate_dashboard_summary(self) -> Dict[str, Any]:
        """
        Generate summary data for dashboard

        Key metrics at a glance.
        """
        if not self.schedule.entries:
            return {"error": "No schedule data"}

        # Calculate metrics
        total_jobs = len(set(e.job_id for e in self.schedule.entries))
        total_machines = len(set(e.machine_id for e in self.schedule.entries))

        # Completion stats
        complete = sum(1 for e in self.schedule.entries if e.status.value == "complete")
        in_progress = sum(
            1 for e in self.schedule.entries if e.status.value == "running"
        )
        pending = sum(1 for e in self.schedule.entries if e.status.value == "pending")

        # Time range
        start = min(e.start_time for e in self.schedule.entries)
        end = max(e.end_time for e in self.schedule.entries)
        total_hours = (end - start).total_seconds() / 3600

        # Utilization
        avg_utilization = (
            sum(self.schedule.machine_utilization.values())
            / len(self.schedule.machine_utilization)
            if self.schedule.machine_utilization
            else 0
        )

        return {
            "summary": {
                "total_jobs": total_jobs,
                "total_machines": total_machines,
                "schedule_span_hours": round(total_hours, 1),
                "makespan_minutes": self.schedule.makespan,
                "total_tardiness_minutes": self.schedule.total_tardiness,
            },
            "status_breakdown": {
                "complete": complete,
                "in_progress": in_progress,
                "pending": pending,
                "total": len(self.schedule.entries),
            },
            "utilization": {
                "average": round(avg_utilization * 100, 1),
                "by_machine": {
                    k: round(v * 100, 1)
                    for k, v in self.schedule.machine_utilization.items()
                },
            },
            "performance": {
                "solver_status": self.schedule.solver_status,
                "solve_time_seconds": round(self.schedule.solve_time, 2),
                "optimality_gap": self.schedule.optimality_gap,
            },
        }


class ScheduleReporter:
    """
    Generates reports from schedules

    Creates:
    - Text-based reports
    - CSV exports
    - Comparison reports
    - Bottleneck analysis
    """

    def __init__(self, schedule: Schedule):
        self.schedule = schedule
        self.visualizer = ScheduleVisualizer(schedule)

    def generate_text_report(self) -> str:
        """Generate human-readable text report"""
        lines = []

        lines.append("=" * 60)
        lines.append("SHOP SCHEDULE REPORT")
        lines.append("=" * 60)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Schedule ID: {self.schedule.schedule_id}")
        lines.append("")

        # Summary
        dashboard = self.visualizer.generate_dashboard_summary()
        summary = dashboard.get("summary", {})

        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Jobs: {summary.get('total_jobs', 0)}")
        lines.append(f"Total Machines: {summary.get('total_machines', 0)}")
        lines.append(f"Schedule Span: {summary.get('schedule_span_hours', 0)} hours")
        lines.append(f"Makespan: {summary.get('makespan_minutes', 0)} minutes")
        lines.append(
            f"Total Tardiness: {summary.get('total_tardiness_minutes', 0)} minutes"
        )
        lines.append("")

        # Machine schedules
        lines.append("MACHINE SCHEDULES")
        lines.append("-" * 40)

        timelines = self.visualizer.generate_machine_timeline()
        for machine_id, entries in timelines.items():
            lines.append(f"\n{machine_id}:")
            for entry in entries:
                lines.append(
                    f"  {entry['job']}/{entry['operation']}: "
                    f"{entry['start'][11:16]} - {entry['end'][11:16]} "
                    f"({entry['duration']} min)"
                )

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def export_to_csv(self, filepath: str):
        """Export schedule to CSV for Excel/analysis"""
        import csv

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Entry ID",
                    "Job ID",
                    "Operation ID",
                    "Machine ID",
                    "Start Time",
                    "End Time",
                    "Duration (min)",
                    "Status",
                    "Expected Duration",
                ]
            )

            for entry in self.schedule.entries:
                writer.writerow(
                    [
                        entry.entry_id,
                        entry.job_id,
                        entry.operation_id,
                        entry.machine_id,
                        entry.start_time.isoformat(),
                        entry.end_time.isoformat(),
                        entry.get_duration(),
                        entry.status.value,
                        entry.expected_duration,
                    ]
                )

    def generate_comparison_report(self, other_schedule: Schedule) -> Dict[str, Any]:
        """
        Compare this schedule with another

        Useful for what-if analysis.
        """
        comparison = {
            "makespan_diff": self.schedule.makespan - other_schedule.makespan,
            "tardiness_diff": self.schedule.total_tardiness
            - other_schedule.total_tardiness,
            "utilization_comparison": {},
        }

        # Compare utilization by machine
        all_machines = set(self.schedule.machine_utilization.keys()) | set(
            other_schedule.machine_utilization.keys()
        )

        for machine_id in all_machines:
            self_util = self.schedule.machine_utilization.get(machine_id, 0)
            other_util = other_schedule.machine_utilization.get(machine_id, 0)

            comparison["utilization_comparison"][machine_id] = {
                "this": round(self_util * 100, 1),
                "other": round(other_util * 100, 1),
                "diff": round((self_util - other_util) * 100, 1),
            }

        return comparison

    def identify_bottlenecks(self, top_n: int = 3) -> List[Dict[str, Any]]:
        """
        Identify bottleneck machines

        Bottlenecks are machines with highest utilization or
        most jobs waiting.
        """
        bottlenecks = []

        for machine_id, utilization in self.schedule.machine_utilization.items():
            # Get entries for this machine
            machine_entries = [
                e for e in self.schedule.entries if e.machine_id == machine_id
            ]

            # Calculate waiting time (queue)
            total_wait = sum(
                max(0, (e.start_time - e.end_time).total_seconds() / 60)
                for e in machine_entries
            )

            bottlenecks.append(
                {
                    "machine_id": machine_id,
                    "utilization": round(utilization * 100, 1),
                    "job_count": len(machine_entries),
                    "total_wait_minutes": int(total_wait),
                    "severity": "high"
                    if utilization > 0.9
                    else "medium"
                    if utilization > 0.7
                    else "low",
                }
            )

        # Sort by utilization (descending)
        bottlenecks.sort(key=lambda x: x["utilization"], reverse=True)

        return bottlenecks[:top_n]


# Convenience functions


def visualize_schedule(schedule: Schedule, output_format: str = "json") -> str:
    """
    Quick visualization function

    Args:
        schedule: Schedule to visualize
        output_format: "json", "html", or "text"

    Returns:
        Visualization data as string
    """
    visualizer = ScheduleVisualizer(schedule)
    reporter = ScheduleReporter(schedule)

    if output_format == "json":
        gantt = visualizer.generate_gantt_data()
        return gantt.to_json()

    elif output_format == "html":
        # Return HTML with embedded visualization
        dashboard = visualizer.generate_dashboard_summary()
        return f"""
        
            Schedule Dashboard
            
                Makespan: {dashboard.get("summary", {}).get("makespan_minutes", 0)} min
                Avg Utilization: {dashboard.get("utilization", {}).get("average", 0)}%
                Status: {dashboard.get("performance", {}).get("solver_status", "Unknown")}
            
            
                
                    
                    Jobs: {dashboard.get("summary", {}).get("total_jobs", 0)}
                    
                    
                    Machines: {dashboard.get("summary", {}).get("total_machines", 0)}
                    
                    
                    Complete: {dashboard.get("status_breakdown", {}).get("complete", 0)}
                    
                
            
        
        """

    elif output_format == "text":
        return reporter.generate_text_report()

    else:
        raise ValueError(f"Unknown format: {output_format}")
